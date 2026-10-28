import asyncio
import sys
from pathlib import Path

import pytest
from PIL import Image as PILImage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class Rect:
    left, top, right, bottom = 0, 0, 1000, 800
    def width(self): return self.right - self.left
    def height(self): return self.bottom - self.top


class Window:
    handle = 1
    title = "test"
    def rectangle(self): return Rect()
    def window_text(self): return self.title
    def set_focus(self): pass
    def capture_as_image(self): return PILImage.new("RGB", (1000, 800), "white")


@pytest.fixture
def backend(monkeypatch):
    b = server.Sketchpad()
    w = Window()
    monkeypatch.setattr(b, "window", lambda: w)
    monkeypatch.setattr(b, "target", lambda: (w, "main"))
    monkeypatch.setattr(b, "text_state", lambda w: ["1. match point A"])
    return b, w


def test_observation_is_single_use(backend):
    b, w = backend
    token = b.observe()[0]["observation_id"]
    assert b.consume(token) is w
    with pytest.raises(ValueError, match="Stale"):
        b.consume(token)


def test_double_click_uses_supported_absolute_input(backend, monkeypatch):
    b, w = backend
    calls = []
    monkeypatch.setattr(server, "backend", b)
    w.click_input = lambda **kwargs: calls.append(kwargs)
    token = b.observe()[0]["observation_id"]
    server.sketchpad_double_click(token, 200, 300)
    assert calls == [{"coords": (200, 300), "absolute": True, "double": True}]


@pytest.mark.parametrize('status,expected', [
    ('拖动以创建一个角度标记', True),
    ('拖动以创建自由绘图', False),
])
def test_angle_mark_never_draws_freehand(backend, monkeypatch, status, expected):
    from pywinauto import mouse
    b, w = backend
    calls = []
    monkeypatch.setattr(server, 'backend', b)
    monkeypatch.setattr(b, 'tool', lambda *args: None)
    monkeypatch.setattr(b, 'text_state', lambda _: [status])
    monkeypatch.setattr(mouse, 'move', lambda **kwargs: None)
    monkeypatch.setattr(server.time, 'sleep', lambda _: None)
    w.drag_mouse_input = lambda **kwargs: calls.append(kwargs)
    result = server.sketchpad_add_angle_mark(b.observe()[0]['observation_id'], 200, 300, -22, 22)
    assert result['status'] == ('input_sent' if expected else 'stopped')
    assert calls == ([{'src': (200, 300), 'dst': (178, 322), 'absolute': True}] if expected else [])


@pytest.mark.parametrize('offsets', [(0, 22), (22, 7), (81, 22)])
def test_angle_mark_invalid_offset_rejected_before_desktop(offsets):
    with pytest.raises(ValueError, match='offsets'):
        server.sketchpad_add_angle_mark('unused', 200, 300, *offsets)


def test_caption_size_uses_numeric_dropdown(backend, monkeypatch):
    from types import SimpleNamespace
    b, w = backend
    selected = []
    font = SimpleNamespace(is_visible=lambda: True, is_enabled=lambda: True, window_text=lambda: 'Times New Roman',
                           item_texts=lambda: ['Arial', 'Times New Roman'])
    size = SimpleNamespace(is_visible=lambda: True, is_enabled=lambda: True, window_text=lambda: '16',
                           item_texts=lambda: ['16', '20', '24'], select=selected.append)
    w.descendants = lambda **kwargs: [font, size]
    monkeypatch.setattr(server, 'backend', b)
    server.sketchpad_set_caption_size(b.observe()[0]['observation_id'], 20)
    assert selected == ['20']


def test_caption_size_unsupported_value_rejected():
    with pytest.raises(ValueError, match='standard'):
        server.sketchpad_set_caption_size('unused', 999)


def test_caption_size_editable_combo_targets_child_edit(backend, monkeypatch):
    from types import SimpleNamespace
    b, w = backend
    events = []
    edit = SimpleNamespace(set_edit_text=lambda s: events.append(('set', s)),
                           type_keys=lambda s: events.append(('key', s)))
    combo = SimpleNamespace(is_visible=lambda: True, is_enabled=lambda: True,
                            window_text=lambda: '16', item_texts=lambda: [],
                            children=lambda **kwargs: [edit])
    w.descendants = lambda **kwargs: [combo]
    monkeypatch.setattr(server, 'backend', b)
    server.sketchpad_set_caption_size(b.observe()[0]['observation_id'], 24)
    assert events == [('set', '24'), ('key', '{ENTER}')]


def test_open_rejects_missing_file_before_desktop_access(tmp_path):
    with pytest.raises(ValueError, match="existing"):
        server.sketchpad_open_file("unused", str(tmp_path / "missing.gsp"), 12, 16)


def test_open_rejects_existing_document_before_input(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / "existing.gsp"
    source.write_bytes(b"test")
    def unexpected(*args):
        raise AssertionError("No file dialog input should be sent")
    controls = [SimpleNamespace(class_name=lambda: "Edit", set_edit_text=unexpected),
                SimpleNamespace(class_name=lambda: "Button", window_text=lambda: "打开", click_input=unexpected)]
    backend = SimpleNamespace(lock=server.threading.RLock(), observed_kind="dialog",
        observed_controls=controls, consume=lambda *a, **k: SimpleNamespace(window_text=lambda: "打开"),
        documents=lambda: [SimpleNamespace(handle=123, window_text=lambda: source.name)])
    monkeypatch.setattr(server, "backend", backend)
    with pytest.raises(ValueError, match="already open"):
        server.sketchpad_open_file("token", str(source), 0, 1)


@pytest.mark.parametrize("handle,valid", [(0, False), (123, False), (123, True)])
def test_foreground_root_handles_transient_invalid_windows(monkeypatch, handle, valid):
    import win32gui
    monkeypatch.setattr(win32gui, "GetForegroundWindow", lambda: handle)
    monkeypatch.setattr(win32gui, "IsWindow", lambda _: valid)
    def ancestor(h, flag):
        assert h and valid
        return 456
    monkeypatch.setattr(win32gui, "GetAncestor", ancestor)
    assert server.foreground_root() == (456 if handle and valid else 0)


def test_foreground_document_wins_over_cached_document():
    a, b = Window(), Window()
    a.handle, b.handle = 10, 20
    assert server.choose_document([a, b], 20, 10) is b
    assert server.choose_document([a, b], 999, 10) is a
    with pytest.raises(RuntimeError, match="uniquely"):
        server.choose_document([a, b], 999)


@pytest.mark.parametrize('active_handle', [123, 456])
def test_mdi_activation_checks_actual_active_child(monkeypatch, active_handle):
    import win32con
    import win32gui
    from types import SimpleNamespace
    b = server.Sketchpad()
    mdi = SimpleNamespace(handle=10)
    main = SimpleNamespace(descendants=lambda **kwargs: [mdi])
    document = SimpleNamespace(handle=123, parent=lambda: mdi)
    monkeypatch.setattr(b, 'window', lambda: main)
    monkeypatch.setattr(b, 'focus', lambda w: None)
    calls = []
    def send(handle, message, param, extra):
        calls.append(message)
        return active_handle if message == win32con.WM_MDIGETACTIVE else 0
    monkeypatch.setattr(win32gui, 'SendMessage', send)
    if active_handle == 123:
        assert b.activate_document(document) is main
    else:
        with pytest.raises(RuntimeError, match='activation failed'):
            b.activate_document(document)
    assert calls == [win32con.WM_MDIACTIVATE, win32con.WM_MDIGETACTIVE]


@pytest.mark.parametrize("title,expected", [
    ("几何画板 - [02-same-sign-triangle.gsp]", "02-same-sign-triangle.gsp"),
    ("几何画板 - [图1.gsp*]", "图1.gsp"), ("几何画板", None),
])
def test_document_filename(title, expected):
    assert server.document_filename(title) == expected


@pytest.mark.parametrize("label", ["隐藏文本(&H)", "隐藏直线(&H)", "隐藏平行线(&H)", "隐藏对象(&H)"])
def test_hide_selection_resolves_accelerators_and_dynamic_captions(backend, monkeypatch, label):
    from types import SimpleNamespace
    b, w = backend
    calls = []
    hide = SimpleNamespace(text=lambda: label + "\tCtrl+H", is_enabled=lambda: True,
                           select=lambda: calls.append("hide"))
    display = SimpleNamespace(text=lambda: "显示(&D)", sub_menu=lambda: SimpleNamespace(items=lambda: [hide]))
    w.menu = lambda: SimpleNamespace(items=lambda: [display])
    monkeypatch.setattr(server, "backend", b)
    server.sketchpad_hide_selected(b.observe()[0]["observation_id"])
    assert calls == ["hide"]


def test_document_change_invalidates_observation(backend):
    b, w = backend
    token = b.observe()[0]["observation_id"]
    w.title = "another document"
    with pytest.raises(ValueError, match="changed"):
        b.consume(token)


@pytest.mark.parametrize("x,y", [(-1, 300), (1000, 300), (100, 20), (100, 790)])
def test_bounds_reject_non_canvas(backend, x, y):
    with pytest.raises(ValueError):
        backend[0].point(backend[1], x, y)


def test_protocol_and_image_content():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(Path(server.__file__))])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert "sketchpad_get_function_guide" in {t.name for t in tools}
                guidance = await session.call_tool("sketchpad_get_function_guide", {"task": "intersection"})
                assert not guidance.isError
                assert "pending_ui_trial_in_toolbox_coordinates" in str(guidance.content)
                search = await session.call_tool('sketchpad_get_function_guide', {'query':'文字跟随点', 'limit':1})
                assert not search.isError
                assert 'attached_text' in str(search.content)
                assert 'needs_modifier_menu_support' in str(search.content)
                assert "sketchpad_batch" in {t.name for t in tools}
                assert "sketchpad_select_and_construct" in {t.name for t in tools}
                assert "sketchpad_enter_inverse_function" in {t.name for t in tools}
                assert "sketchpad_verify_saved_file" in {t.name for t in tools}
                assert "sketchpad_construct" in {t.name for t in tools}
                assert "sketchpad_select_custom_tool" in {t.name for t in tools}
                result = await session.call_tool("sketchpad_select_custom_tool", {"observation_id": "stale", "path": ["box", "tool"]})
                assert result.isError
                assert "Stale" in str(result.content)
                # Rejected before any desktop access; checks real transport and error handling.
                result = await session.call_tool("sketchpad_click", {"observation_id": "stale", "x": 200, "y": 200})
                assert result.isError
                assert "Stale" in str(result.content)
    asyncio.run(run())


def test_screenshot_becomes_mcp_image(backend, monkeypatch):
    monkeypatch.setattr(server, "backend", backend[0])
    async def run():
        result = await server.mcp.call_tool("sketchpad_observe", {})
        content = result[0] if isinstance(result, tuple) else result
        assert any(getattr(c, "type", None) == "image" for c in content)
    asyncio.run(run())


def test_observation_returns_custom_tool_and_status(backend):
    b, _ = backend
    b.active_custom_tool = ["box", "tool"]
    info = b.observe()[0]
    assert info["active_custom_tool"] == ["box", "tool"]
    assert info["visible_text"] == ["1. match point A"]


def test_dialog_blocks_canvas_actions(backend, monkeypatch):
    b, w = backend
    token = b.observe()[0]["observation_id"]
    monkeypatch.setattr(b, "target", lambda: (w, "dialog"))
    with pytest.raises(ValueError, match="dialog"):
        b.consume(token)


class Control:
    handle = 12
    def __init__(self, name="Edit", enabled=True):
        self.name, self.enabled = name, enabled
    def class_name(self): return self.name
    def is_enabled(self): return self.enabled


def test_parameter_field_must_still_exist(backend, monkeypatch):
    b, w = backend
    c = Control()
    b.observed_kind, b.observed_controls = "dialog", [c]
    monkeypatch.setattr(w, "descendants", lambda: [c], raising=False)
    assert b.dialog_control(w, 0, "Edit") is c
    monkeypatch.setattr(w, "descendants", lambda: [])
    with pytest.raises(ValueError, match="changed"):
        b.dialog_control(w, 0, "Edit")


@pytest.mark.parametrize("index,kind", [(-1, "Edit"), (1, "Edit"), (0, "Button")])
def test_dialog_control_indices_and_types(backend, index, kind):
    b, w = backend
    b.observed_kind, b.observed_controls = "dialog", [Control()]
    with pytest.raises(ValueError): b.dialog_control(w, index, kind)


def test_file_dialog_not_editable(backend):
    b, w = backend
    w.title = "另存为"
    b.observed_kind, b.observed_controls = "dialog", [Control()]
    with pytest.raises(ValueError, match="manually"):
        b.dialog_control(w, 0, "Edit")


def test_screenshot_coordinates_account_for_window_origin(backend, monkeypatch):
    b, w = backend
    r = Rect()
    r.left, r.top, r.right, r.bottom = 200, 100, 1200, 900
    monkeypatch.setattr(w, "rectangle", lambda: r)
    assert b.point(w, 300, 250) == (500, 350)


def test_lightweight_observation_skips_capture(backend, monkeypatch):
    b, w = backend
    def unexpected_capture():
        raise AssertionError("No image should be captured")
    monkeypatch.setattr(w, "capture_as_image", unexpected_capture)
    result = b.observe(include_image=False)
    assert len(result) == 1
    assert b.consume(result[0]["observation_id"]) is w


def test_image_observation_focuses_target_before_capture(backend, monkeypatch):
    b, w = backend
    events = []
    capture = w.capture_as_image
    monkeypatch.setattr(b, "focus", lambda target: events.append("focus"))
    monkeypatch.setattr(w, "capture_as_image", lambda: (events.append("capture"), capture())[1])
    b.observe()
    assert events == ["focus", "capture"]


def test_batch_stops_after_document_transition(backend, monkeypatch):
    b, w = backend
    monkeypatch.setattr(server, "backend", b)
    calls = []
    def action(observation_id, key):
        b.consume(observation_id, allow_dialog=True)
        calls.append(key)
        w.title = "changed"
    monkeypatch.setattr(server, "sketchpad_key", action)
    token = b.observe()[0]["observation_id"]
    result = server.sketchpad_batch(token, [
        {"tool": "sketchpad_key", "args": {"key": "escape"}},
        {"tool": "sketchpad_key", "args": {"key": "enter"}},
    ])
    assert result["status"] == "stopped"
    assert result["completed"] == 1
    assert calls == ["escape"]


def test_batch_rejects_unknown_action_before_input(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, "backend", b)
    token = b.observe()[0]["observation_id"]
    with pytest.raises(ValueError, match="Unsupported"):
        server.sketchpad_batch(token, [
            {"tool": "sketchpad_key", "args": {"key": "escape"}},
            {"tool": "sketchpad_save_to_new_file", "args": {}},
        ])
    assert b.token == token


def test_batch_caption_plan_validated_before_input(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, 'backend', b)
    token = b.observe()[0]['observation_id']
    with pytest.raises(ValueError, match='Caption text'):
        server.sketchpad_batch(token, [
            {'tool': 'sketchpad_key', 'args': {'key': 'right'}},
            {'tool': 'sketchpad_type_literal', 'args': {'text': 'x'*8193}},
        ])
    assert b.token == token


def test_batch_caption_and_template_navigation(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, 'backend', b)
    events = []
    def literal(observation_id: str, text: str):
        b.consume(observation_id)
        events.append(text)
    def key(observation_id: str, key: str):
        b.consume(observation_id)
        events.append(key)
    monkeypatch.setattr(server, 'sketchpad_type_literal', literal)
    monkeypatch.setattr(server, 'sketchpad_key', key)
    result = server.sketchpad_batch(b.observe()[0]['observation_id'], [
        {'tool': 'sketchpad_type_literal', 'args': {'text': '|k₁|'}},
        {'tool': 'sketchpad_key', 'args': {'key': 'tab'}},
        {'tool': 'sketchpad_type_literal', 'args': {'text': '2'}},
    ])
    assert result['status'] == 'completed'
    assert events == ['|k₁|', 'tab', '2']
