"""Read-only manual guidance, kept separate from verified desktop recipes."""
import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from workflows import get_workflow

RULES_PATH = Path(__file__).with_name('function_rules.json')


WORKFLOW_LINKS = {
    "finite_coordinates": "toolbox_coordinates",
    "intersection": "constrained_intersections",
    "dynamic_area": "dynamic_fill",
    "fraction_caption": "fraction_annotation",
}


@lru_cache(maxsize=4)
def _read_rules(path, modified_ns, size):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load():
    stat = RULES_PATH.stat()
    return _read_rules(str(RULES_PATH), stat.st_mtime_ns, stat.st_size)


def _normalized(value):
    return re.sub(r'[\W_]+', '', value.casefold())


def _matches(rules, query, limit):
    phrase = _normalized(query)
    grams = {phrase[i:i+2] for i in range(len(phrase)-1)}
    matches = []
    for rule in rules:
        terms = [rule['id'], rule['intent'], *rule.get('aliases', [])]
        exact = [term for term in terms if len(_normalized(term)) >= 2 and _normalized(term) in phrase]
        overlap = max((len(grams & {s[i:i+2] for i in range(len(s)-1)})
                       for s in map(_normalized, terms)), default=0)
        if not exact and overlap < 2:
            continue
        score = sum(len(_normalized(term))*4 for term in exact)+overlap
        matches.append((score, rule['id'], exact))
    return sorted(matches, key=lambda row: (-row[0], row[1]))[:limit]


def get_function_guide(task=None, query=None, limit=3):
    if task is not None and query is not None:
        raise ValueError('Choose task or query, not both.')
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError('limit must be 1 to 5.')
    if query is not None and (not isinstance(query, str) or not query.strip() or len(query) > 256):
        raise ValueError('Provide a nonempty query of at most 256 characters.')
    data = _load()
    result = {"evidence": data["evidence"], "source": data["source"],
              "scope": data.get('manual_scope'),
              "preflight": deepcopy(data["preflight"]),
              "failure_policy": deepcopy(data.get('failure_policy', []))}
    if query is not None:
        result.update(query=query, candidates=[
            dict(task=identifier, match_score=score, matched_terms=terms,
                 **get_function_guide(identifier))
            for score, identifier, terms in _matches(data['rules'], query, limit)])
        result['routing_note'] = '候选规则是功能选择依据，不会执行操作；没有合适候选时查询实际脚本，不自动套用无关流程。'
        return result
    if task is None:
        result["tasks"] = [{"task": rule["id"], "intent": rule["intent"],
                            "category": rule.get('category'),
                            "automation_status": rule.get('automation_status')}
                           for rule in data["rules"]]
        return result
    rule = next((rule for rule in data["rules"] if rule["id"] == task), None)
    if rule is None:
        raise ValueError("Unknown task; call sketchpad_get_function_guide without task to list supported tasks.")
    result["rule"] = deepcopy(rule)
    # Only attach existing evidence; a manual rule does not promote UI verification.
    if task in WORKFLOW_LINKS:
        result["workflow"] = get_workflow(WORKFLOW_LINKS[task])
    return result
