"""Tests for idea_eval.persona_pressure — advisory 'why I wouldn't buy this' sub-step."""

from __future__ import annotations

from idea_core.llm import LLMResponse, MockBackend
from idea_eval.evaluate import KILL, PURSUE, REVIEW, Evaluation
from idea_eval.persona_pressure import run_persona_pressure

_POOL = [
    {"persona": "蒙语母语中老年人", "domain": "mongolian.elderly"},
    {"persona": "中国英语学习者", "domain": "english_learner"},
]


def _idea(id_):
    return {"id": id_, "title": "标题", "pain": "痛点", "solution": "方案"}


def test_only_runs_against_pursue_survivors():
    calls = []

    def responder(req):
        calls.append(req.id)
        return LLMResponse(id=req.id, ok=True, data={"objection": "太贵了不会买"})

    evals = [
        Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90),
        Evaluation(idea_id="b", title="B", verdict=REVIEW, eval_score=50),
        Evaluation(idea_id="c", title="C", verdict=KILL, eval_score=10),
    ]
    ideas_by_id = {"a": _idea("a"), "b": _idea("b"), "c": _idea("c")}
    run_persona_pressure(evals, ideas_by_id, MockBackend(responder), {"user_template": "{title}"}, persona_pool=_POOL)

    assert len(calls) == 2  # 1 pursue candidate x 2 personas
    a = next(e for e in evals if e.idea_id == "a")
    assert len(a.persona_objections) == 2
    assert {o["persona"] for o in a.persona_objections} == {"蒙语母语中老年人", "中国英语学习者"}
    assert all(o["objection"] == "太贵了不会买" for o in a.persona_objections)
    # review/kill untouched
    assert next(e for e in evals if e.idea_id == "b").persona_objections == []
    assert next(e for e in evals if e.idea_id == "c").persona_objections == []


def test_noop_when_pool_empty():
    evals = [Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)]
    run_persona_pressure(evals, {"a": _idea("a")}, MockBackend(), {"user_template": "{title}"}, persona_pool=[])
    assert evals[0].persona_objections == []


def test_noop_when_no_pursue_survivors():
    evals = [Evaluation(idea_id="a", title="A", verdict=REVIEW, eval_score=50)]
    calls = []
    run_persona_pressure(
        evals, {"a": _idea("a")},
        MockBackend(lambda req: calls.append(req.id) or LLMResponse(id=req.id, data={"objection": "x"})),
        {"user_template": "{title}"}, persona_pool=_POOL,
    )
    assert calls == []


def test_respects_personas_per_candidate_limit():
    calls = []

    def responder(req):
        calls.append(req.id)
        return LLMResponse(id=req.id, ok=True, data={"objection": "x"})

    evals = [Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)]
    run_persona_pressure(
        evals, {"a": _idea("a")}, MockBackend(responder), {"user_template": "{title}"},
        persona_pool=_POOL, personas_per_candidate=1,
    )
    assert len(calls) == 1
    assert len(evals[0].persona_objections) == 1


def test_ignores_failed_or_empty_responses():
    def responder(req):
        return LLMResponse(id=req.id, ok=False, error="boom")

    evals = [Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)]
    run_persona_pressure(evals, {"a": _idea("a")}, MockBackend(responder), {"user_template": "{title}"}, persona_pool=_POOL)
    assert evals[0].persona_objections == []
