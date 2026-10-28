import asyncio
import importlib.util
from pathlib import Path

import pytest

import server
from test_server import Rect, backend


class Control:
    def __init__(self, handle, kind="Button", text="OK", enabled=True):
        self.handle, self.kind, self.text, self.enabled = handle, kind, text, enabled
        self.rect = Rect()
        self.clicks = 0

    def rectangle(self): return self.rect
    def class_name(self): return self.kind
    def window_text(self): return self.text
    def is_enabled(self): return self.enabled
    def is_visible(self): return True
    def click_input(self): self.clicks += 1


def dialog(backend, monkeypatch, controls):
    b, w = backend
    w.title = "New calculator"
    monkeypatch.setattr(b, "target", lambda: (w, "dialog"))
    monkeypatch.setattr(w, "descendants", lambda: controls, raising=False)
    return b.observe(include_image=False)[0]["observation_id"]


def key_action(key):
    return {"tool": "sketchpad_key", "args": {"key": key}}


def test_batch_rejects_invalid_later_argument_before_any_input(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, "backend", b)
    token = b.observe()[0]["observation_id"]
    with pytest.raises(ValueError):
        server.sketchpad_batch(token, [key_action("escape"),
            {"tool": "sketchpad_click", "args": {"x": "300", "y": 300}}])
    assert b.token == token


def test_batch_rejects_invalid_key_before_any_input(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, "backend", b)
    token = b.observe()[0]["observation_id"]
    with pytest.raises(ValueError, match="Unsupported key"):
        server.sketchpad_batch(token, [key_action("escape"), key_action("bad")])
    assert b.token == token


def test_batch_binds_original_control_layout(backend, monkeypatch):
    b, _ = backend
    controls = [Control(10, text="1"), Control(11, text="2")]
    token = dialog(backend, monkeypatch, controls)
    monkeypatch.setattr(server, "backend", b)
    calls = []
    def action(observation_id, control_index):
        b.consume(observation_id, allow_dialog=True)
        calls.append(control_index)
        controls.reverse()
    monkeypatch.setattr(server, "sketchpad_click_dialog_button", action)
    result = server.sketchpad_batch(token, [
        {"tool": "sketchpad_click_dialog_button", "args": {"control_index": 0}},
        {"tool": "sketchpad_click_dialog_button", "args": {"control_index": 1}},
    ])
    assert result["status"] == "stopped"
    assert calls == [0]
    assert [a["outcome"] for a in result["actions"]] == ["input_sent", "not_attempted"]


@pytest.mark.parametrize("change", ["text", "handle", "rectangle"])
def test_single_action_rejects_changed_dialog_control(backend, monkeypatch, change):
    b, _ = backend
    controls = [Control(10)]
    token = dialog(backend, monkeypatch, controls)
    if change == "text": controls[0].text = "Delete"
    elif change == "handle": controls[0].handle = 20
    else:
        controls[0].rect = Rect()
        controls[0].rect.left = 40
    with pytest.raises(ValueError, match="controls changed"):
        b.consume(token, allow_dialog=True)


def test_edit_content_and_button_enabled_changes_are_expected(backend, monkeypatch):
    b, _ = backend
    controls = [Control(10, "Edit", ""), Control(11, enabled=False)]
    token = dialog(backend, monkeypatch, controls)
    controls[0].text = "6/x"
    controls[1].enabled = True
    assert b.consume(token, allow_dialog=True) is backend[1]


def test_partial_input_failure_is_explicitly_unknown(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, "backend", b)
    calls = []
    def action(observation_id, key):
        b.consume(observation_id)
        calls.append(key)
        if key == "enter": raise RuntimeError("Input sent, then transport failed")
    monkeypatch.setattr(server, "sketchpad_key", action)
    token = b.observe()[0]["observation_id"]
    result = server.sketchpad_batch(token, [key_action("escape"), key_action("enter"), key_action("tab")])
    assert calls == ["escape", "enter"]
    assert result["completed"] == 1
    assert [a["outcome"] for a in result["actions"]] == ["input_sent", "outcome_unknown", "not_attempted"]
    assert b.token is None


def test_refresh_failure_preserves_sent_input(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, "backend", b)
    monkeypatch.setattr(server, "sketchpad_key", lambda observation_id, key: b.consume(observation_id))
    token = b.observe()[0]["observation_id"]
    def failed_refresh(**kwargs): raise RuntimeError("Capture unavailable")
    monkeypatch.setattr(b, "observe", failed_refresh)
    result = server.sketchpad_batch(token, [key_action("escape"), key_action("tab")])
    assert result["completed"] == 1
    assert result["actions"][0]["outcome"] == "input_sent"
    assert result["actions"][1]["outcome"] == "not_attempted"


def test_toolbar_cache_revalidates_and_avoids_tree_search(backend, monkeypatch):
    import pywinauto
    b, w = backend
    button = Control(10, "CheckBox", server.TOOLS["point"])
    searches = []
    class UIA:
        def window(self, **kwargs): return self
        def descendants(self, **kwargs):
            searches.append(kwargs)
            return [button]
    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: UIA())
    b.tool(w, "point")
    b.tool(w, "point")
    assert len(searches) == 1
    assert button.clicks == 2
    button.rect = Rect()
    button.rect.left = 42
    b.tool(w, "point")
    assert len(searches) == 2


def test_toolbar_does_not_retry_a_failed_click(backend, monkeypatch):
    import pywinauto
    b, w = backend
    button = Control(10, "CheckBox", server.TOOLS["point"])
    def failed_click():
        button.clicks += 1
        raise RuntimeError("Click result unknown")
    button.click_input = failed_click
    class UIA:
        def window(self, **kwargs): return self
        def descendants(self, **kwargs): return [button]
    monkeypatch.setattr(pywinauto, "Desktop", lambda **kwargs: UIA())
    with pytest.raises(RuntimeError): b.tool(w, "point")
    assert button.clicks == 1


def test_inverse_function_uses_observed_button_captions(backend, monkeypatch):
    b, w = backend
    controls = [Control(i + 10, text=t) for i, t in enumerate(["确定", "&x", "/", "6", "-"])]
    dialog(backend, monkeypatch, controls)
    w.title = "新建函数"
    token = b.observe(include_image=False)[0]["observation_id"]
    monkeypatch.setattr(server, "backend", b)
    plans = []
    monkeypatch.setattr(server, "sketchpad_batch", lambda token, actions: plans.extend(actions) or {"status": "completed"})
    server.sketchpad_enter_inverse_function(token, -6)
    assert [p["args"]["control_index"] for p in plans] == [4, 3, 2, 1, 0]


def test_inverse_function_refuses_missing_buttons(backend, monkeypatch):
    b, w = backend
    dialog(backend, monkeypatch, [Control(10, text="确定")])
    w.title = "新建函数"
    token = b.observe(include_image=False)[0]["observation_id"]
    monkeypatch.setattr(server, "backend", b)
    with pytest.raises(ValueError, match="calculator button"):
        server.sketchpad_enter_inverse_function(token, 6)
    assert b.token == token


def test_preflight_rejects_destructive_button_before_earlier_action(backend, monkeypatch):
    b, _ = backend
    token = dialog(backend, monkeypatch, [Control(10, text="Delete")])
    monkeypatch.setattr(server, "backend", b)
    with pytest.raises(ValueError, match="manually"):
        server.sketchpad_batch(token, [key_action("escape"),
            {"tool": "sketchpad_click_dialog_button", "args": {"control_index": 0}}])
    assert b.token == token


def test_select_and_construct_is_one_native_plan(backend, monkeypatch):
    plans = []
    monkeypatch.setattr(server, "sketchpad_batch", lambda token, actions: plans.extend(actions) or {})
    server.sketchpad_select_and_construct("observed", "parallel", [[300, 400], [500, 600]], clear_at=[800, 900])
    assert plans[0]["args"] == {"tool": "select"}
    assert plans[1] == {"tool": "sketchpad_click", "args": {"x": 800, "y": 900}}
    assert plans[-1] == {"tool": "sketchpad_construct", "args": {"construction": "parallel"}}
    with pytest.raises(ValueError):
        server.sketchpad_select_and_construct("observed", "parallel", [[300, 400]])
    with pytest.raises(ValueError, match="clear_at"):
        server.sketchpad_select_and_construct("observed", "parallel", [[300, 400], [500, 600]])


def test_verify_save_checks_header_and_active_document(backend, monkeypatch, tmp_path):
    b, w = backend
    monkeypatch.setattr(server, "backend", b)
    dest = tmp_path / "native.gsp"
    dest.write_bytes(b"GSP4" + b"sample")
    w.title = "Sketchpad - [native.gsp]"
    token = b.observe()[0]["observation_id"]
    result = server.sketchpad_verify_saved_file(token, str(dest))
    assert result["status"] == "file_verified"
    assert result["geometry_verified"] is False
    dest.write_bytes(b"image")
    token = b.observe()[0]["observation_id"]
    with pytest.raises(ValueError, match="header"):
        server.sketchpad_verify_saved_file(token, str(dest))


BRIDGE_PATH = Path(__file__).resolve().parents[3] / "work" / "native_bridge.py"


@pytest.mark.skipif(not BRIDGE_PATH.exists(), reason="Local development bridge is not installed")
@pytest.mark.parametrize("transition,error,expect_image", [(False, False, False), (True, False, True), (False, True, True)])
def test_bridge_only_captures_scalar_edits_on_transitions_or_errors(transition, error, expect_image):
    spec = importlib.util.spec_from_file_location("native_bridge_test", BRIDGE_PATH)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    before = {"observation_id": "before", "window_handle": 1, "kind": "dialog", "title": "calculator"}
    calls = []
    async def call(name, args):
        calls.append((name, args))
        if name != "sketchpad_observe": return {"error": error, "result": []}
        state = dict(before, observation_id="after", window_handle=2 if transition else 1)
        return {"error": False, "result": [state]}
    result, token, state = asyncio.run(bridge.process_request(call,
        {"name": "sketchpad_set_dialog_field", "args": {"control_index": 1, "value": "5"}}, "before", before))
    image_calls = [args for name, args in calls if name == "sketchpad_observe" and args.get("include_image")]
    assert bool(image_calls) is expect_image
    assert token == "after"
    assert result["error"] is error


@pytest.mark.skipif(not BRIDGE_PATH.exists(), reason="Local development bridge is not installed")
def test_bridge_preserves_action_result_when_observation_transport_fails():
    spec = importlib.util.spec_from_file_location("native_bridge_failure_test", BRIDGE_PATH)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    async def call(name, args):
        if name == "sketchpad_observe": raise RuntimeError("Desktop disconnected")
        return {"error": False, "result": [{"status": "completed", "completed": 3}]}
    result, token, state = asyncio.run(bridge.process_request(call,
        {"name": "sketchpad_batch", "args": {"actions": []}}, "observed", {}))
    assert result["result"][0]["completed"] == 3
    assert result["observation"]["error"] is True
    assert token is None and state is None
