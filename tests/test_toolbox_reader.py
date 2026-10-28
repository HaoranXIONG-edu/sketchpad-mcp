import struct

import pytest

from toolbox_reader import FormatError, index_array, label, parse_bytes, records


def record(tag, payload=b""):
    return struct.pack("<II", len(payload), tag) + payload


def object_record(text, parents=()):
    name = text.encode("utf-8")
    header = struct.pack("<5H", 1, 0, 0, 0, 4)
    style = bytes(22) + struct.pack("<H", len(name)) + name + b"\0"
    refs = struct.pack("<I", len(parents)) + b"".join(struct.pack("<I", p) for p in parents)
    return record(2000, header) + record(2005, style) + record(2002, refs) + record(2007)


def toolbox(order=(2, 1), parents=(1,)):
    header = bytes(24) + struct.pack("<I", 2)
    refs = struct.pack("<I", len(order)) + b"".join(struct.pack("<I", p) for p in order)
    return (b"GSP4" + record(1002, header) + record(1100, b"example\0padding")
            + object_record("origin") + object_record("bound", parents)
            + record(1204, refs) + record(1003))


@pytest.mark.parametrize("data", [b"GSP5", b"GSP4x", b"GSP4" + struct.pack("<II", 100, 1)])
def test_rejects_wrong_magic_and_truncation(data):
    with pytest.raises(FormatError):
        list(records(data))


def test_rejects_bad_index_count():
    with pytest.raises(FormatError):
        index_array(struct.pack("<II", 2, 1))


def test_chinese_label_uses_byte_length():
    text = "坐标原点".encode("utf-8")
    payload = bytes(22) + struct.pack("<H", len(text)) + text + b"\0"
    assert label(payload)["text"] == "坐标原点"
    assert label(payload[:-1]) is None


def test_input_order_is_independent_of_storage_order():
    result = parse_bytes(toolbox())
    tool = result["tools"][0]
    assert result["structural_bytes_consumed"] == len(toolbox())
    assert tool["name"] == "example"
    assert [i["label"]["text"] for i in tool["inputs_candidate"]] == ["bound", "origin"]
    assert tool["objects"][1]["parents"] == [1]
    assert tool["structural_issues"] == []


def test_invalid_references_are_explicitly_reported():
    tool = parse_bytes(toolbox(order=(2, 2, 9), parents=(9,)))["tools"][0]
    assert "Invalid or duplicate input references" in tool["structural_issues"]
    assert any("out-of-range parent" in issue for issue in tool["structural_issues"])


def test_unterminated_tool_is_rejected():
    with pytest.raises(FormatError, match="ended inside"):
        parse_bytes(toolbox()[:-8])


def test_mcp_inspection_reads_file_without_desktop(tmp_path, monkeypatch):
    import server
    (tmp_path / "sample.gsp").write_bytes(toolbox())
    monkeypatch.setenv("SKETCHPAD_TOOL_FOLDER", str(tmp_path))
    summary = server.sketchpad_inspect_toolbox("sample.gsp")
    assert summary["tool_count"] == 1
    detail = server.sketchpad_inspect_toolbox("sample.gsp", "example")
    assert detail["tool"]["input_order_candidate"] == [2, 1]
    with pytest.raises(ValueError, match="exact relative_file"):
        server.sketchpad_inspect_toolbox("../sample.gsp")
    with pytest.raises(ValueError, match="missing or ambiguous"):
        server.sketchpad_inspect_toolbox("sample.gsp", "missing")
