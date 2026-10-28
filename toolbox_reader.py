"""Read-only, partial structural decoder for local GSP4 toolbox files.

Tags and field meanings are inferred from this installation's files, not an
official format specification. Unknown data stays opaque; never execute text.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import time


class FormatError(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    offset: int
    tag: int
    payload: bytes


def records(data: bytes):
    if data[:4] != b"GSP4":
        raise FormatError("Only the observed GSP4 container is supported")
    offset = 4
    while offset < len(data):
        if len(data) - offset < 8:
            raise FormatError(f"Truncated record header at {offset}")
        size, tag = struct.unpack_from("<II", data, offset)
        end = offset + 8 + size
        if end > len(data):
            raise FormatError(f"Record at {offset} exceeds file boundary")
        yield Record(offset, tag, data[offset + 8:end])
        offset = end


def decode_text(data):
    data = data.split(b"\0", 1)[0]
    for encoding in ("utf-8", "gbk"):
        try:
            return {"text": data.decode(encoding), "encoding": encoding}
        except UnicodeDecodeError:
            pass
    return {"text": None, "encoding": None, "raw_hex": data.hex()}


def index_array(data):
    if len(data) < 4:
        raise FormatError("Missing index count")
    count = struct.unpack_from("<I", data)[0]
    if len(data) != 4 + count * 4:
        raise FormatError("Index count does not match payload length")
    return list(struct.unpack_from(f"<{count}I", data, 4)) if count else []


def label(data):
    if len(data) < 24:
        return None
    size = struct.unpack_from("<H", data, 22)[0]
    if 24 + size >= len(data) or data[24 + size] != 0:
        return None
    return decode_text(data[24:24 + size])


def parse_bytes(data: bytes, source="<memory>"):
    tools, warnings = [], []
    tool = obj = None
    counts = Counter()
    for record in records(data):
        counts[record.tag] += 1
        p, tag, payload = record.offset, record.tag, record.payload
        if tag == 1002:
            if tool is not None:
                raise FormatError(f"Nested or unterminated tool at {p}")
            tool = {"offset": p, "name": None, "objects": [], "input_order_candidate": None,
                    "input_order_verification": "inferred_from_tag_1204_not_ui_verified",
                    "declared_object_count_candidate": struct.unpack_from("<I", payload, 24)[0]
                    if len(payload) >= 28 else None, "metadata": []}
        elif tag == 1003:
            if tool is None or obj is not None:
                raise FormatError(f"Unmatched tool end at {p}")
            tool["end_offset"] = p + 8 + len(payload)
            finalize_tool(tool)
            tools.append(tool)
            tool = None
        elif tool is not None:
            if tag == 2000:
                if obj is not None or len(payload) < 10:
                    raise FormatError(f"Unsupported object header at {p}")
                fields = list(struct.unpack_from(f"<{len(payload) // 2}H", payload)) if len(payload) % 2 == 0 else []
                obj = {"id": len(tool["objects"]) + 1, "offset": p,
                       "construction_code": struct.unpack_from("<H", payload)[0],
                       "header_u16": fields, "label": None, "parents": [],
                       "attributes": [], "semantic_operation": None}
            elif tag == 2007:
                if obj is None:
                    raise FormatError(f"Unmatched object end at {p}")
                obj["end_offset"] = p + 8 + len(payload)
                tool["objects"].append(obj)
                obj = None
            elif obj is not None:
                attribute = {"tag": tag, "offset": p, "bytes": len(payload)}
                if tag == 2002:
                    obj["parents"] = index_array(payload)
                elif tag == 2005:
                    obj["label"] = label(payload)
                elif tag == 2008 and len(payload) == 2:
                    attribute["raw_u16"] = struct.unpack_from("<H", payload)[0]
                elif tag in (2300, 2307) and len(payload) >= 18:
                    # These records contain structured caption/formula markup.
                    size = struct.unpack_from("<H", payload, 16)[0]
                    if 18 + size < len(payload) and payload[18 + size] == 0:
                        attribute["text_candidate"] = decode_text(payload[18:18 + size])
                obj["attributes"].append(attribute)
            elif tag == 1100:
                name = decode_text(payload)
                tool["name"] = name["text"]
                tool["name_encoding"] = name["encoding"]
            elif tag == 1204:
                tool["input_order_candidate"] = index_array(payload)
                tool["input_order_record_offset"] = p
            elif tag == 9007:
                tool["description"] = decode_text(payload)
            else:
                tool["metadata"].append({"tag": tag, "offset": p, "bytes": len(payload)})
    if obj is not None or tool is not None:
        raise FormatError("File ended inside a tool or object")
    return {"source": str(source), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "header": "GSP4", "structural_bytes_consumed": len(data),
            "record_count": sum(counts.values()), "record_tags": dict(sorted(counts.items())),
            "tool_count": len(tools), "object_count": sum(len(t["objects"]) for t in tools),
            "decode_level": "partial_structure_not_executable_script",
            "warnings": warnings + ["Tag 1204 candidate order is not a mandatory UI click sequence; matching can be automatic."], "tools": tools}


def finalize_tool(tool):
    objects = tool["objects"]
    order = tool["input_order_candidate"]
    issues = []
    if tool["declared_object_count_candidate"] != len(objects):
        issues.append("Declared object count differs from parsed count")
    if order is not None:
        if len(set(order)) != len(order) or any(not 1 <= ref <= len(objects) for ref in order):
            issues.append("Invalid or duplicate input references")
        tool["inputs_candidate"] = [
            {"order": i + 1, "object_id": ref, "label": objects[ref - 1]["label"],
             "construction_code": objects[ref - 1]["construction_code"],
             "raw_match_type_candidate": objects[ref - 1]["header_u16"][4]}
            for i, ref in enumerate(order) if 1 <= ref <= len(objects)]
    else:
        issues.append("No input-order record found")
        tool["inputs_candidate"] = []
    for obj in objects:
        invalid = [ref for ref in obj["parents"] if not 1 <= ref <= len(objects)]
        if invalid:
            issues.append(f"Object {obj['id']} has out-of-range parent references: {invalid}")
    tool["structural_issues"] = issues
    tool["dependency_edge_count"] = sum(len(obj["parents"]) for obj in objects)


def parse_file(path):
    path = Path(path)
    return parse_bytes(path.read_bytes(), source=path.resolve())


def compact(result):
    return {key: result[key] for key in ("source", "sha256", "bytes", "header", "record_count",
            "tool_count", "object_count", "decode_level", "warnings")} | {"tools": [
                {key: t[key] for key in ("name", "offset", "end_offset", "inputs_candidate",
                    "input_order_verification", "structural_issues", "dependency_edge_count")}
                | {"object_count": len(t["objects"])} for t in result["tools"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.source.glob("*.gsp")) if args.source.is_dir() else [args.source]
    results, errors = [], []
    started = time.perf_counter()
    for path in paths:
        try:
            result = parse_file(path)
            results.append(compact(result))
            if path.name.startswith(("07 ", "08 ", "09 ")) or not args.source.is_dir():
                (args.output / (path.stem + ".json")).write_text(
                    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except (OSError, ValueError, struct.error) as exc:
            errors.append({"source": str(path), "error": str(exc)})
    index = {"format": "experimental_gsp4_toolbox_index_v1", "read_only": True,
             "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
             "files_parsed": len(results), "files_failed": len(errors),
             "total_tools": sum(r["tool_count"] for r in results),
             "files": results, "errors": errors}
    (args.output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in index.items() if k not in ("files", "errors")}, ensure_ascii=False))
    if errors:
        print(json.dumps(errors, ensure_ascii=False))


if __name__ == "__main__":
    main()
