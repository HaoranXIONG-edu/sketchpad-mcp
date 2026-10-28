from contextlib import contextmanager

import pytest

import server
from custom_tools import caption, describe, installed_toolboxes, resolve


class Item:
    def __init__(self, name, child=None, enabled=True):
        self.name, self.child, self.enabled = name, child, enabled
        self.clicked = False
    def text(self): return self.name
    def sub_menu(self): return self.child
    def is_enabled(self): return self.enabled
    def click_input(self): self.clicked = True
    def get_properties(self): return {"state": 128}


class Menu:
    def __init__(self, *items): self.values = list(items)
    def items(self): return self.values


@pytest.fixture
def menu():
    return Menu(Item("创建新工具..."), Item("工具选项..."), Item("-- 工具文件夹 --"),
                Item("03 三角形", Menu(Item("等边三角形"), Item("内心"))),
                Item("44 分形工具", Menu(Item("深层", Menu(Item("任意新工具"))))))


def test_browse_all_categories_and_recursive_paths(menu):
    result = describe(menu, [], 3)
    assert [e["name"] for e in result["entries"]] == ["03 三角形", "44 分形工具"]
    leaf = result["entries"][1]["children"][0]["children"][0]
    assert leaf["path"] == ["44 分形工具", "深层", "任意新工具"]
    assert leaf["kind"] == "tool"


def test_exact_resolve_and_no_selection_during_browse(menu):
    child, item = resolve(menu, ["03 三角形", "内心"])
    assert child is None and not item.clicked
    describe(menu, [], 3)
    assert not item.clicked


def test_repeated_category_names():
    leaf = Item("leaf")
    root = Menu(Item("same", Menu(Item("same", Menu(leaf)))))
    assert resolve(root, ["same", "same", "leaf"])[1] is leaf


@pytest.mark.parametrize("path", [["missing"], ["创建新工具..."], ["03 三角形", "内心", "extra"], [""]])
def test_invalid_or_management_paths_rejected(menu, path):
    with pytest.raises(ValueError): resolve(menu, path)


def test_duplicate_and_disabled_paths_rejected():
    with pytest.raises(ValueError, match="ambiguous"):
        resolve(Menu(Item("a"), Item("a")), ["a"])
    with pytest.raises(ValueError, match="disabled"):
        resolve(Menu(Item("a", enabled=False)), ["a"])


def test_bounded_discovery_reports_truncation(menu):
    assert describe(menu, [], 8, limit=2)["truncated"] is True
    with pytest.raises(ValueError): describe(menu, [], 0)


def test_inventory_includes_all_files_and_nested_folders(tmp_path, monkeypatch):
    for i in range(44): (tmp_path / f"{i:02d} toolbox.gsp").write_bytes(b"GSP4")
    (tmp_path / "new").mkdir()
    (tmp_path / "new" / "future.gsp").write_bytes(b"GSP4")
    (tmp_path / "ignore.txt").write_text("ignore")
    monkeypatch.setenv("SKETCHPAD_TOOL_FOLDER", str(tmp_path))
    result = installed_toolboxes()
    assert result["count"] == 45
    assert any(t["name"] == "future" for t in result["toolboxes"])


def test_select_custom_tool_requires_leaf(monkeypatch, menu):
    @contextmanager
    def popup(w): yield menu
    monkeypatch.setattr(server, "DesktopMenus", popup)
    monkeypatch.setattr(server.backend, "consume", lambda token: object())
    navigated = []
    monkeypatch.setattr(server, "activate_menu_path", lambda root, path: navigated.append(path) or [])
    with pytest.raises(ValueError, match="category"):
        server.sketchpad_select_custom_tool("test", ["03 三角形"])
    result = server.sketchpad_select_custom_tool("test", ["03 三角形", "内心"])
    assert result["drawing_completed"] is False
    assert navigated == [["03 三角形", "内心"]]


def test_browse_returns_next_observe(monkeypatch, menu):
    @contextmanager
    def popup(w): yield menu
    monkeypatch.setattr(server, "DesktopMenus", popup)
    monkeypatch.setattr(server.backend, "consume", lambda token: object())
    result = server.sketchpad_list_custom_tools("test", ["44 分形工具"], 2)
    assert result["entries"][0]["children"][0]["name"] == "任意新工具"
    assert result["next"] == "sketchpad_observe"


def test_menu_caption_preserves_tool_names():
    assert caption("&01 Tool (A)\tCtrl+1") == "01 Tool (A)"


def test_keyboard_navigation_counts_disabled_items_and_separators(monkeypatch):
    import custom_tools
    import pywinauto.keyboard
    sent = []
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent.append(keys))
    root = Menu(Item("disabled", enabled=False), Item("", enabled=False),
                Item("category", Menu(Item("leaf"))))
    trace = custom_tools.activate_menu_path(root, ["category", "leaf"])
    assert sent == ["{HOME}{DOWN}{DOWN}", "{RIGHT}", "{HOME}", "{ENTER}"]
    assert trace[0]["position"] == 2


def test_keyboard_navigation_checks_highlight_before_committing(monkeypatch):
    import custom_tools
    import pywinauto.keyboard
    sent = []
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent.append(keys))
    item = Item("leaf")
    item.get_properties = lambda: {"state": 0}
    with pytest.raises(RuntimeError, match="not highlighted"):
        custom_tools.activate_menu_path(Menu(item), ["leaf"])
    assert sent == ["{HOME}"]


@pytest.mark.parametrize("selected", [False, True])
def test_picker_long_press_and_cleanup(monkeypatch, menu, selected):
    import pywinauto
    import pywinauto.controls.menuwrapper as wrappers
    import custom_tools
    state = {"open": 0, "released": False, "escapes": 0}
    class Button:
        def press_mouse_input(self, **kwargs):
            assert kwargs["absolute"] is False
            state["open"] = 1
        def release_mouse_input(self, **kwargs):
            assert kwargs["absolute"] is False
            state["released"] = True
    class Popup:
        def process_id(self): return 99
        def menu(self): return type("NativeMenu", (), {"handle": 123})()
    class Window:
        handle = 1
        def process_id(self): return 99
        def type_keys(self, key):
            assert key == "{ESC}"
            state["open"] = max(0, state["open"] - 1)
            state["escapes"] += 1
    class Desktop:
        def __init__(self, **kwargs): pass
        def window(self, **kwargs): return self
        def descendants(self, **kwargs): return [Button()]
        def windows(self, **kwargs): return [Popup()] if state["open"] else []
    monkeypatch.setattr(pywinauto, "Desktop", Desktop)
    monkeypatch.setattr(wrappers, "Menu", lambda *args, **kwargs: menu)
    monkeypatch.setattr(custom_tools.time, "sleep", lambda seconds: None)
    with custom_tools.DesktopMenus(Window()) as root:
        assert root is menu and state["released"]
        # A selected tool leaves no popup; browsing can leave nested popups.
        state["open"] = 0 if selected else 2
    assert state["open"] == 0
    assert state["escapes"] == (1 if selected else 3)
