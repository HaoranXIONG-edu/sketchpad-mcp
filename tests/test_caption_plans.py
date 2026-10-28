import pytest

import server
from caption_plans import caption_plan, FORMULAS
from test_server import backend


@pytest.mark.parametrize('formula,fractions', [
    ('curve_k1', 1), ('curve_k2', 1), ('area_difference', 0),
    ('area_half_difference', 2), ('area_sum', 0), ('area_half_sum', 1),
])
def test_native_formula_templates_are_bounded_and_exit_placeholders(formula, fractions):
    actions = caption_plan(formula, [880, 750], [950, 750])
    assert 1 <= len(actions) <= 32
    clicks = [a['args'] for a in actions if a['tool'] == 'sketchpad_click']
    assert clicks.count({'x': 880, 'y': 750}) == fractions
    assert clicks.count({'x': 950, 'y': 750}) == int(formula.startswith('area_'))
    right = [a for a in actions if a == {'tool': 'sketchpad_key', 'args': {'key': 'right'}}]
    assert len(right) == 2*(fractions+int(formula.startswith('area_')))
    for action in actions:
        server.argument_model(getattr(server, action['tool'])).model_validate(action['args'])


@pytest.mark.parametrize('point', [None, [880], [880, True], ['880', 750]])
def test_template_coordinates_must_be_observed_pixel_pairs(point):
    with pytest.raises(ValueError, match='current screenshot'):
        caption_plan('curve_k1', point)


def test_caption_refuses_unconfirmed_editing_without_batch(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, 'backend', b)
    def unexpected(*args):
        raise AssertionError('No formula input is allowed')
    monkeypatch.setattr(server, 'sketchpad_batch', unexpected)
    result = server.sketchpad_fill_math_caption(b.observe()[0]['observation_id'], 'curve_k1', [880, 750])
    assert result['status'] == 'stopped'


def test_caption_runs_one_batch_after_live_context_check(backend, monkeypatch):
    b, _ = backend
    monkeypatch.setattr(server, 'backend', b)
    monkeypatch.setattr(b, 'text_state', lambda _: ['点击以停止正在编辑的文本'])
    plans = []
    def batch(token, actions):
        b.consume(token)
        plans.append(actions)
        return {'status': 'completed'}
    monkeypatch.setattr(server, 'sketchpad_batch', batch)
    result = server.sketchpad_fill_math_caption(b.observe()[0]['observation_id'],
        'area_half_difference', [880, 750], [950, 750])
    assert len(plans) == 1
    assert result['formula_verified'] is False


def test_already_selected_tool_does_not_click_again(backend, monkeypatch):
    import pywinauto
    from test_optimization import Control
    b, w = backend
    button = Control(10, 'CheckBox', server.TOOLS['select'])
    button.get_toggle_state = lambda: 1
    class UIA:
        def window(self, **kwargs): return self
        def descendants(self, **kwargs): return [button]
    monkeypatch.setattr(pywinauto, 'Desktop', lambda **kwargs: UIA())
    assert b.tool(w, 'select')['already_selected'] is True
    assert button.clicks == 0
    button.get_toggle_state = lambda: 0
    assert b.tool(w, 'select')['already_selected'] is False
    assert button.clicks == 1
