import pytest

from function_guide import get_function_guide


def test_every_listed_task_resolves_with_prerequisites():
    catalog = get_function_guide()
    assert catalog["tasks"]
    for task in catalog["tasks"]:
        result = get_function_guide(task["task"])
        assert result["rule"]["requires"]
        assert result["rule"]["pitfalls"]
        assert result["evidence"] == "manual_read_not_ui_verified"


def test_manual_and_desktop_evidence_remain_distinct():
    result = get_function_guide("intersection")
    assert result["workflow"]["verification"] == "pending_ui_trial_in_toolbox_coordinates"
    assert get_function_guide("finite_coordinates")["workflow"]["verification"] == "ui_and_saved_native_objects_verified"
    assert "workflow" not in get_function_guide("curve_sampling")


def test_callers_cannot_change_cached_guidance():
    result = get_function_guide("dynamic_area")
    result["preflight"].clear()
    result["rule"]["requires"].clear()
    result["workflow"]["steps"].clear()
    fresh = get_function_guide("dynamic_area")
    assert fresh["preflight"] and fresh["rule"]["requires"] and fresh["workflow"]["steps"]


def test_invalid_task_does_not_fall_back_to_unrelated_action():
    with pytest.raises(ValueError, match="Unknown task"):
        get_function_guide("missing")


def test_all_procedures_have_actionable_contracts_and_valid_sources():
    tasks = get_function_guide()['tasks']
    identifiers = [t['task'] for t in tasks]
    assert len(identifiers) == len(set(identifiers))
    for identifier in identifiers:
        rule = get_function_guide(identifier)['rule']
        assert rule['selection'] and len(rule['steps']) >= 3
        assert len(rule['success_checks']) >= 2
        assert rule['stop_conditions'] and rule['recovery'] and rule['automation_status']
        start, end = rule['manual_pages']['printed_range']
        assert 1 <= start <= end <= 212
        assert rule['manual_pages']['pdf_range'] == [start+1, end+1]
        assert set(rule['related_tasks']) <= set(identifiers)


@pytest.mark.parametrize('query,expected', [
    ('标注跟着点移动', 'attached_text'),
    ('同页多个坐标系串用', 'multi_coordinates'),
    ('动态系数', 'parameter_binding'),
    ('整页复制', 'copy_page_dependencies'),
    ('热文本', 'dynamic_text'),
    ('曲线不平滑', 'curve_sampling'),
])
def test_intent_query_routes_to_relevant_procedure(query, expected):
    result = get_function_guide(query=query, limit=1)
    assert result['candidates'][0]['task'] == expected
    assert result['candidates'][0]['rule']['steps']
    assert result['evidence'] == 'manual_read_not_ui_verified'


def test_unrelated_query_does_not_propose_an_action():
    assert get_function_guide(query='未知量子态')['candidates'] == []


@pytest.mark.parametrize('kwargs', [
    {'task':'intersection', 'query':'求交点'}, {'query':''}, {'query':'x'*257},
    {'query':'坐标', 'limit':0}, {'query':'坐标', 'limit':True},
])
def test_query_validation(kwargs):
    with pytest.raises(ValueError):
        get_function_guide(**kwargs)


def test_search_results_do_not_mutate_rules_or_failure_policy():
    result = get_function_guide(query='文字跟随点', limit=1)
    result['candidates'][0]['rule']['steps'].clear()
    result['failure_policy'].clear()
    fresh = get_function_guide('attached_text')
    assert fresh['rule']['steps'] and fresh['failure_policy']
    assert fresh['rule']['automation_status'] == 'needs_modifier_menu_support'
    assert 'workflow' not in fresh


def test_rule_file_updates_do_not_need_service_restart(tmp_path, monkeypatch):
    import json
    import os
    import function_guide
    data = json.loads(function_guide.RULES_PATH.read_text(encoding='utf-8'))
    path = tmp_path/'rules.json'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(function_guide, 'RULES_PATH', path)
    before = get_function_guide('finite_coordinates')['rule']['intent']
    stamp = path.stat().st_mtime_ns
    data['rules'][0]['intent'] = '更新后的坐标规则'
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.utime(path, ns=(stamp+1_000_000, stamp+1_000_000))
    assert get_function_guide('finite_coordinates')['rule']['intent'] != before


def test_public_guide_query_never_accesses_desktop(monkeypatch):
    import server
    def unexpected(*args, **kwargs):
        raise AssertionError('Rule lookup must not access the desktop')
    monkeypatch.setattr(server.backend, 'window', unexpected)
    assert server.sketchpad_get_function_guide(query='整页复制', limit=1)['candidates']
