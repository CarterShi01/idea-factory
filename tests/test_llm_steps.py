"""Tests for the wired-in LLM steps: A (generate_llm) and B (judge_survivors).

All offline: a MockBackend with a canned responder stands in for the real LLM,
so these exercise the wiring without any network or Claude Code.
"""

from datetime import date

import pytest

from idea_factory.runtime.llm import LLMResponse, MockBackend, PendingHandoff
from idea_factory.contract.models import KILL, PURSUE
from idea_factory.stages.diligence.critique import critique_survivors
from idea_factory.stages.diligence.gate import evaluate_all
from idea_factory.stages.diligence.judge import judge_survivors
from idea_factory import pipeline
from idea_factory.contract import artifacts
from idea_factory.contract.models import Evaluation
from idea_factory.stages.generate.llm import generate_llm
from idea_factory.stages.recall.normalize import normalize_record

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

    res = pipeline.run(
        data_dir="data",
        output_dir=tmp_path,
        today=REF_DATE,
        to_stage="rank",
        generate_backend="mock",
        backends={"generate": MockBackend(responder)},
    )
    assert res.stage("generate").survived > 0
    assert artifacts.load_items(tmp_path, "rank")


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
    def responder(req):
        return LLMResponse(
            id=req.id,
            data={"verdict": "review", "score": 50, "killer_objection": "meh", "cheap_experiment": "t"},
        )

    pipeline.run(
        data_dir="data",
        output_dir=tmp_path,
        today=REF_DATE,
        version=False,
        judge_backend="mock",
        critique=False,
        backends={"judge": MockBackend(responder)},
    )
    evals = [Evaluation.from_dict(d) for d in artifacts.load_items(tmp_path, "diligence")]
    assert any(e.judged_by == "llm" for e in evals)


# --- B-prep: devil's advocate critique ----------------------------------


def test_critique_populates_evaluation_fields():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "objections": ["no real wedge", "TAM is tiny", "no distribution"],
                "killer_objection": "no real wedge",
                "doomed_assumption": "founders will pay for this at all",
            },
        )

    out = critique_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert e.critique == ["no real wedge", "TAM is tiny", "no distribution"]
    assert e.critique_killer == "no real wedge"
    assert e.doomed_assumption == "founders will pay for this at all"


def test_judge_sees_critique_in_user_prompt_and_records_rebuttal():
    """End-to-end critique → judge: judge prompt must receive the critique block,
    and the judge's rebuttal must land on the Evaluation."""
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def critique_responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "objections": ["uniqueness-token-XYZ-from-critique"],
                "killer_objection": "uniqueness-token-XYZ-from-critique",
                "doomed_assumption": "founders pay",
            },
        )

    critique_survivors(evals, {"i1": ideas[0]}, MockBackend(critique_responder), {"user_template": "{title}"})

    seen_user_prompts: list[str] = []

    def judge_responder(req):
        seen_user_prompts.append(req.user)
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 55,
                "respond_to_critique": "驳回 uniqueness 反驳——我们有 X 切入点",
                "killer_objection": "distribution",
                "cheap_experiment": "landing page",
            },
        )

    # use the actual judge template so the {critique} placeholder is exercised
    judge_template = "标题：{title}\n反驳：\n{critique}\n请评估。"
    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(judge_responder), {"user_template": judge_template})

    assert any("uniqueness-token-XYZ-from-critique" in p for p in seen_user_prompts), (
        "judge prompt must include the critique block"
    )
    e = out[0]
    assert e.judge_rebuttal.startswith("驳回")
    assert e.judged_by == "llm"


def test_pipeline_runs_critique_then_judge(tmp_path):
    """The pipeline should call critique first, then judge — verify by counting hits."""
    critique_calls = {"n": 0}
    judge_calls = {"n": 0}

    def critique_responder(req):
        critique_calls["n"] += 1
        return LLMResponse(
            id=req.id,
            data={"objections": ["weak"], "killer_objection": "weak", "doomed_assumption": "x"},
        )

    def judge_responder(req):
        judge_calls["n"] += 1
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 50,
                "respond_to_critique": "ack",
                "killer_objection": "weak",
                "cheap_experiment": "t",
            },
        )

    pipeline.run(
        data_dir="data",
        output_dir=tmp_path,
        today=REF_DATE,
        version=False,
        judge_backend="mock",
        critique=True,
        backends={"judge": MockBackend(judge_responder), "critique": MockBackend(critique_responder)},
    )
    evals = [Evaluation.from_dict(d) for d in artifacts.load_items(tmp_path, "diligence")]
    n_survivors = sum(1 for e in evals if e.verdict in ("pursue", "review"))
    assert critique_calls["n"] == n_survivors
    assert judge_calls["n"] == n_survivors
    assert any(e.critique for e in evals)
    assert any(e.judge_rebuttal == "ack" for e in evals)


def test_pipeline_skips_critique_when_disabled(tmp_path):
    critique_calls = {"n": 0}

    def critique_responder(req):
        critique_calls["n"] += 1
        return LLMResponse(id=req.id, data={"objections": []})

    def judge_responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 50,
                "respond_to_critique": "",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    pipeline.run(
        data_dir="data",
        output_dir=tmp_path,
        today=REF_DATE,
        version=False,
        judge_backend="mock",
        critique=False,
        backends={"judge": MockBackend(judge_responder), "critique": MockBackend(critique_responder)},
    )
    assert critique_calls["n"] == 0


# --- P0(2): anti-bias controls -------------------------------------------


def test_judge_records_confidence():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 50,
                "confidence": "medium",
                "respond_to_critique": "ack",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    assert out[0].judge_confidence == "medium"
    assert out[0].confidence_demoted is False
    assert out[0].verdict == "review"  # unchanged


def test_low_confidence_pursue_is_demoted_to_review():
    """Anti-overconfidence: when the LLM says pursue but admits low confidence,
    the system forces a review (human audit lane), not an auto-pursue."""
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "pursue",
                "score": 72,
                "confidence": "low",
                "respond_to_critique": "ack",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert e.verdict == "review"
    assert e.confidence_demoted is True
    assert e.eval_score == 72  # score preserved — only verdict changes


def test_low_confidence_kill_is_demoted_to_review():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "kill",
                "score": 20,
                "confidence": "low",
                "respond_to_critique": "weak",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    assert out[0].verdict == "review"
    assert out[0].confidence_demoted is True


def test_high_confidence_kill_is_not_demoted():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "kill",
                "score": 15,
                "confidence": "high",
                "respond_to_critique": "no defense",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    assert out[0].verdict == KILL
    assert out[0].confidence_demoted is False


def test_build_request_reads_model_from_env(monkeypatch):
    """model_env lets each step (generate/critique/judge) bind to a different
    model so generation ≠ evaluation isn't enforced by a single global default."""
    from idea_factory.runtime.llm import build_request

    monkeypatch.setenv("MY_TEST_MODEL_VAR", "tc-think")
    config = {"system": "s", "model_env": "MY_TEST_MODEL_VAR"}
    req = build_request("id1", "u", config)
    assert req.model == "tc-think"


def test_build_request_falls_back_when_env_missing(monkeypatch):
    from idea_factory.runtime.llm import build_request

    monkeypatch.delenv("MY_TEST_MODEL_VAR", raising=False)
    config = {"system": "s", "model_env": "MY_TEST_MODEL_VAR", "model": "fallback-model"}
    req = build_request("id1", "u", config)
    assert req.model == "fallback-model"


# --- P0(3): judge 5-dim sub-scores ---------------------------------------


def test_judge_scores_persist_when_all_five_dims_present():
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 50,
                "confidence": "medium",
                "scores": {
                    "pain_real": 0.6,
                    "solo_buildable": 0.4,
                    "reachable": 0.5,
                    "defensible": 0.3,
                    "timing": 0.7,
                },
                "respond_to_critique": "ack",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert e.judge_scores == {
        "pain_real": 0.6,
        "solo_buildable": 0.4,
        "reachable": 0.5,
        "defensible": 0.3,
        "timing": 0.7,
    }
    # avg 0.5 * 100 = 50, top-level = 50 -> no disagreement flag
    assert not any("自相矛盾" in f for f in e.risk_flags)


def test_judge_score_disagreement_flagged():
    """Top-level score 80 vs 5-dim avg 0.2*100=20 → gap=60 → flag self-contradiction."""
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "pursue",
                "score": 80,
                "confidence": "high",
                "scores": {
                    "pain_real": 0.2,
                    "solo_buildable": 0.2,
                    "reachable": 0.2,
                    "defensible": 0.2,
                    "timing": 0.2,
                },
                "respond_to_critique": "ack",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert any("自相矛盾" in f for f in e.risk_flags)


def test_judge_scores_tolerate_partial_dims():
    """If LLM only fills some sub-dims, we keep what's there and do NOT
    trigger the self-consistency check (insufficient data)."""
    ideas = [_high_factor_idea()]
    evals = evaluate_all(ideas)

    def responder(req):
        return LLMResponse(
            id=req.id,
            data={
                "verdict": "review",
                "score": 50,
                "confidence": "medium",
                "scores": {"pain_real": 0.8, "solo_buildable": 0.5},
                "respond_to_critique": "ack",
                "killer_objection": "x",
                "cheap_experiment": "y",
            },
        )

    out = judge_survivors(evals, {"i1": ideas[0]}, MockBackend(responder), {"user_template": "{title}"})
    e = out[0]
    assert e.judge_scores == {"pain_real": 0.8, "solo_buildable": 0.5}
    assert not any("自相矛盾" in f for f in e.risk_flags)


# --- CC handoff (manual mode) raises, never calls CC ----------------------


def test_gen_cc_backend_raises_pending_handoff(tmp_path):
    with pytest.raises(PendingHandoff) as ei:
        pipeline.run(
            data_dir="data",
            output_dir=tmp_path,
            today=REF_DATE,
            to_stage="rank",
            generate_backend="cc",
            job_dir=tmp_path / "jobs",
        )
    assert ei.value.request_path.exists()  # request pack written for the human
