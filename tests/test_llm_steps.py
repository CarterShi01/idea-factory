"""Tests for the wired-in LLM steps: A (generate_llm) and B (judge_survivors).

All offline: a MockBackend with a canned responder stands in for the real LLM,
so these exercise the wiring without any network or Claude Code.
"""

from datetime import date

import pytest

from idea_core.llm import LLMResponse, MockBackend, PendingHandoff
from idea_eval.evaluate import KILL, PURSUE, evaluate_all, judge_survivors
from idea_eval.pipeline import run_evaluation
from idea_gen.generate import generate_llm
from idea_gen.normalize import normalize_record
from idea_gen.pipeline import run_pipeline

REF_DATE = date(2026, 6, 13)


def _high_factor_idea(idea_id="i1"):
    return {
        "id": idea_id,
        "title": "demo",
        "pain": "founders waste hours manually doing tedious work",
        "solution": "an agent",
        "target_user": "founders",
        "confidence": "real",
        "factors": {
            "market_freshness": 1.0,
            "pain_intensity": 1.0,
            "build_cost": 1.0,
            "moat_signal": 1.0,
            "competition_density": 1.0,
            "distribution_fit": 1.0,
        },
    }


# --- A: generate_llm ------------------------------------------------------


def test_generate_llm_parses_candidates():
    sig = normalize_record({"source_name": "t", "title": "X", "pain": "users waste time"})

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "candidates": [
                    {"title": "Idea A", "pain": "p", "solution": "s", "target_user": "devs"},
                    {"title": "Idea B", "pain": "p2", "solution": "s2", "target_user": "founders"},
                ]
            },
        )

    cands = generate_llm([sig], MockBackend(responder), {"user_template": "{title} {pain_statement}"})
    assert [c.title for c in cands] == ["Idea A", "Idea B"]
    assert cands[0].id == f"{sig.id}-0"
    assert cands[0].signal_id == sig.id


def test_generate_llm_skips_empty_responses():
    sig = normalize_record({"source_name": "t", "title": "X", "pain": "p"})
    cands = generate_llm([sig], MockBackend(), {"user_template": "{title}"})  # default mock -> empty
    assert cands == []


def test_pipeline_gen_backend_mock(tmp_path):
    def responder(req):
        return LLMResponse(
            id=req.id,
            data={"candidates": [{"title": "T", "pain": "p", "solution": "s", "target_user": "u"}]},
        )

    res = run_pipeline(
        data_dir="data",
        output_dir=tmp_path,
        today=REF_DATE,
        gen_backend="mock",
        llm=MockBackend(responder),
    )
    assert res.candidate_count > 0
    assert res.scored


# --- B: judge_survivors ---------------------------------------------------


def test_judge_overrides_rule_verdict():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)
    assert evals[0].verdict == PURSUE  # rule says pursue...

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "kill",
                "score": 12,
                "killer_objection": "no defensibility",
                "cheap_experiment": "landing page test",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert e.judged_by == "llm"
    assert e.verdict == KILL          # ...LLM downgrades it
    assert e.eval_score == 12
    assert e.killer_objection == "no defensibility"


def test_judge_noop_when_no_data():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)
    before = evals[0].verdict
    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(), {"user_template": "{title}"})
    assert out[0].verdict == before
    assert out[0].judged_by == "rule"


def test_eval_pipeline_with_judge_backend(tmp_path):
    gen = run_pipeline(data_dir="data", output_dir=tmp_path, today=REF_DATE)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={"verdict": "review", "score": 50, "killer_objection": "meh", "cheap_experiment": "t"},
        )

    res = run_evaluation(
        input_path=gen.json_path,
        output_dir=tmp_path,
        today=REF_DATE,
        judge_backend="mock",
        llm=MockBackend(responder),
    )
    assert any(e.judged_by == "llm" for e in res.evaluations)


# --- CC handoff (manual mode) raises, never calls CC ----------------------


def test_gen_cc_backend_raises_pending_handoff(tmp_path):
    with pytest.raises(PendingHandoff) as ei:
        run_pipeline(
            data_dir="data",
            output_dir=tmp_path,
            today=REF_DATE,
            gen_backend="cc",
            job_dir=tmp_path / "jobs",
        )
    assert ei.value.request_path.exists()  # request pack written for the human
