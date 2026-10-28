"""Discover custom tool menus without assuming a particular toolbox collection."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

MANAGEMENT = {"创建新工具", "工具选项", "显示脚本视图", "隐藏脚本视图", "选择工具文件夹"}


def caption(text):
    return text.split("\t")[0].replace("&", "").strip()


def is_management(text):
    name = re.sub(r"\([A-Za-z]\)", "", caption(text)).rstrip(".… ")
    return name in MANAGEMENT or "工具文件夹" in name


def entries(menu):
    return [item for item in menu.items() if caption(item.text()) and not is_management(item.text())]


def resolve(menu, path):
    if not isinstance(path, list) or len(path) > 16 or any(not isinstance(p, str) or not p.strip() for p in path):
        raise ValueError("Use a path array copied from list_custom_tools, with at most 16 nonempty names.")
    selected = None
    for index, part in enumerate(path):
        matches = [i for i in entries(menu) if caption(i.text()) == part]
        if len(matches) != 1:
            raise ValueError(f"Tool menu path is missing or ambiguous: {part!r}. List the current menu again.")
        selected = matches[0]
        if not selected.is_enabled():
            raise ValueError(f"Tool menu item is disabled: {part}")
        child = selected.sub_menu()
        if index < len(path) - 1 and child is None:
            raise ValueError(f"Not a toolbox category: {part}")
        menu = child
    return menu, selected


def activate_menu_path(root, path):
    """Use actual menu navigation so popup return values reach Sketchpad's caller."""
    from pywinauto.keyboard import send_keys
    menu = root
    trace = []
    for part in path:
        # Sketchpad's popup counts disabled entries and separators during key navigation.
        items = list(menu.items())
        matches = [index for index, item in enumerate(items) if caption(item.text()) == part]
        if len(matches) != 1:
            raise ValueError("Menu path changed; observe and browse it again")
        index = matches[0]
        item = items[index]
        if not item.is_enabled():
            raise ValueError("Menu item is disabled")
        child = item.sub_menu()
        send_keys("{HOME}" + "{DOWN}" * index, pause=0.04)
        if not item.get_properties().get("state", 0) & 128:
            raise RuntimeError("Intended menu item is not highlighted; selection cancelled")
        send_keys("{RIGHT}" if child is not None else "{ENTER}", pause=0.04)
        trace.append({"caption": part, "position": index})
        menu = child
    return trace


def describe(menu, path, depth=1, limit=3000):
    if not 1 <= depth <= 8:
        raise ValueError("depth must be between 1 and 8.")
    budget = [limit]
    truncated = [False]
    def visit(current, prefix, remaining):
        result = []
        for item in entries(current):
            if budget[0] <= 0:
                truncated[0] = True
                break
            budget[0] -= 1
            name = caption(item.text())
            child = item.sub_menu()
            record = {"name": name, "path": prefix + [name],
                      "enabled": bool(item.is_enabled()),
                      "kind": "category" if child is not None else "tool"}
            if child is not None and remaining > 1 and record["enabled"]:
                record["children"] = visit(child, record["path"], remaining - 1)
            result.append(record)
        return result
    result = visit(menu, path, depth)
    return {"path": path, "entries": result, "truncated": truncated[0],
            "note": "Categories without children in this response can be browsed separately. Tool input counts are not inferred from names; inspect status text or script view."}


def installed_toolboxes():
    exe = Path(os.environ.get("SKETCHPAD_EXE", r"D:\Program Files (x86)\Sketchpad5\GSP5chs.exe"))
    folder = Path(os.environ.get("SKETCHPAD_TOOL_FOLDER", str(exe.parent / "Tool Folder")))
    if not folder.is_dir():
        raise ValueError("Tool folder not found. Set SKETCHPAD_TOOL_FOLDER to the actual folder.")
    files = sorted(folder.rglob("*.gsp"), key=lambda p: str(p.relative_to(folder)).casefold())
    return {"folder": str(folder), "count": len(files), "toolboxes": [
        {"name": p.stem, "relative_file": str(p.relative_to(folder)), "bytes": p.stat().st_size}
        for p in files], "note": "Installed files only. The live custom-tools menu determines which are currently loaded. No toolbox files are copied or modified."}


class DesktopMenus:
    def __init__(self, window):
        self.window = window
        self.menu = None

    def dismiss(self):
        from pywinauto import Desktop
        for _ in range(16):
            popups = [p for p in Desktop(backend="win32").windows(class_name="#32768", visible_only=True)
                      if p.process_id() == self.window.process_id()]
            if not popups:
                return
            self.window.type_keys("{ESC}")
        raise RuntimeError("Custom Tools menu did not close; close it manually and observe again.")

    def __enter__(self):
        from pywinauto import Desktop
        w = self.window
        try:
            self.dismiss()
            # Close an existing menu/unfinished tool before opening the tool picker.
            w.type_keys("{ESC}")
            uia = Desktop(backend="uia").window(handle=w.handle)
            buttons = uia.descendants(title="自定义工具", control_type="CheckBox")
            if len(buttons) != 1:
                raise RuntimeError("Cannot uniquely identify the Custom Tools toolbar button.")
            button = buttons[0]
            # Sketchpad opens this picker on a long press, not a normal click.
            button.press_mouse_input(absolute=False)
            try:
                time.sleep(0.85)
            finally:
                button.release_mouse_input(absolute=False)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                popups = [p for p in Desktop(backend="win32").windows(class_name="#32768", visible_only=True)
                          if p.process_id() == w.process_id()]
                roots = []
                for popup in popups:
                    from pywinauto.controls.menuwrapper import Menu
                    menu = Menu(w, popup.menu().handle, is_main_menu=False)
                    if any("创建新工具" in caption(i.text()) for i in menu.items()):
                        roots.append(menu)
                if len(roots) == 1:
                    self.menu = roots[0]
                    return self.menu
                time.sleep(0.1)
            raise RuntimeError("Custom Tools popup did not appear. Check for a dialog or an unsupported toolbar layout.")
        except Exception:
            self.dismiss()
            raise

    def __exit__(self, exc_type, exc, tb):
        # Escape only while a popup still exists: after choosing a tool, Escape
        # would cancel the tool we just selected.
        self.dismiss()
