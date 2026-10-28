import pytest

import server
from workflows import get_workflow


def test_workflow_separates_trials_from_pending_steps():
    assert {t['task'] for t in get_workflow()['tasks']} == {
        'four_graph_delivery', 'toolbox_coordinates', 'bounded_inverse_function',
        'constrained_intersections', 'dynamic_fill', 'fraction_annotation', 'reference_angle_marks',
        'efficient_four_graph_refinement'}
    assert get_workflow("toolbox_coordinates")["verification"] == "ui_and_saved_native_objects_verified"
    assert get_workflow("dynamic_fill")["verification"] == "pending_ui_trial"
    recipe = get_workflow("bounded_inverse_function")
    assert recipe["native_result"]["bounded_plot_parents"] == [175, 12]
    recipe["steps"].clear()
    assert get_workflow("bounded_inverse_function")["steps"]
    with pytest.raises(ValueError):
        get_workflow("unknown")


@pytest.mark.parametrize("prompt,expected_clicks", [("1. 匹配点 *", 1), ("1. 匹配点 C", 0)])
def test_coordinate_recipe_stops_before_click_for_wrong_tool(monkeypatch, prompt, expected_clicks):
    calls = []
    monkeypatch.setattr(server.backend, "consume", lambda token: object())
    monkeypatch.setattr(server.backend, "point", lambda w, x, y: (x, y))
    monkeypatch.setattr(server.backend, "observe", lambda image: [{"observation_id": "fresh", "visible_text": [prompt]}])
    monkeypatch.setattr(server, "sketchpad_select_custom_tool", lambda *args: calls.append("select"))
    monkeypatch.setattr(server, "sketchpad_click", lambda *args: calls.append("click"))
    result = server.sketchpad_create_toolbox_coordinates("observed", 500, 600)
    assert calls.count("click") == expected_clicks
    assert result["drawing_completed"] is False
    assert result["status"] == ("input_sent" if expected_clicks else "stopped")


@pytest.mark.parametrize("prompt,expected_clicks", [("1. 匹配函数 y=f(x)", 1), ("1. 匹配点 *", 0)])
def test_function_recipe_checks_actual_prompt(monkeypatch, prompt, expected_clicks):
    clicks = []
    monkeypatch.setattr(server.backend, "consume", lambda token: object())
    monkeypatch.setattr(server.backend, "point", lambda w, x, y: (x, y))
    monkeypatch.setattr(server.backend, "observe", lambda image: [{"observation_id": "fresh", "visible_text": [prompt]}])
    monkeypatch.setattr(server, "sketchpad_select_custom_tool", lambda *args: None)
    monkeypatch.setattr(server, "sketchpad_click", lambda *args: clicks.append(args))
    result = server.sketchpad_apply_bounded_function("observed", 170, 347)
    assert len(clicks) == expected_clicks
    assert result["status"] == ("input_sent" if expected_clicks else "stopped")
