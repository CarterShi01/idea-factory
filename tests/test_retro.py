"""Tests for idea_eval.retro — outcome recording + aggregation."""

from __future__ import annotations

from idea_factory.runtime import ledger
from idea_factory.runtime.llm import LLMResponse, MockBackend
from idea_factory.stages.retro import outcomes as retro


def test_record_outcome_writes_ledger(tmp_path):
    out = retro.record_outcome(
        tmp_path, candidate_id="c1", tested_at="2026-07-12",
        metric="signups", actual_value=7.0, target=10.0, horizon_days=7,
        lesson="渠道选错了。",
    )
    assert out.prediction == {"metric": "signups", "target": 10.0, "horizon_days": 7}
    assert out.actual == {"metric": "signups", "value": 7.0}

    stored = ledger.read_outcomes(tmp_path)
    assert len(stored) == 1
    assert stored[0]["candidate_id"] == "c1"


def test_prediction_error_signed_relative():
    assert retro.prediction_error({"prediction": {"target": 10.0}, "actual": {"value": 7.0}}) == -0.3
    assert retro.prediction_error({"prediction": {"target": 10.0}, "actual": {"value": 15.0}}) == 0.5


def test_prediction_error_none_when_no_target():
    assert retro.prediction_error({"prediction": {}, "actual": {"value": 5.0}}) is None
    assert retro.prediction_error({"prediction": {"target": 0}, "actual": {"value": 5.0}}) is None


def test_summarize_outcomes_aggregates(tmp_path):
    retro.record_outcome(tmp_path, "c1", "2026-07-12", "signups", 7.0, target=10.0, lesson="A")
    retro.record_outcome(tmp_path, "c2", "2026-07-13", "signups", 12.0, target=10.0, first_revenue=99.0, lesson="B")

    summary = retro.summarize_outcomes(tmp_path)
    assert summary["count"] == 2
    assert summary["avg_prediction_error"] == -0.05  # avg(-0.3, +0.2)
    assert summary["first_revenue_events"] == 1
    assert summary["lessons"] == ["A", "B"]


def test_summarize_outcomes_empty(tmp_path):
    summary = retro.summarize_outcomes(tmp_path)
    assert summary == {
        "count": 0, "avg_prediction_error": None, "first_revenue_events": 0, "lessons": [],
    }


# --- #7: LLM-assisted lesson extraction -------------------------------------


def test_extract_lesson_llm_uses_verdict_context_and_prediction_gap():
    seen = {}

    def responder(req):
        seen["user"] = req.user
        return LLMResponse(id=req.id, ok=True, data={"lesson": "渠道选错了,通用发帖转化率低"})

    lesson = retro.extract_lesson_llm(
        candidate_id="c1", metric="signups", target=10.0, actual_value=3.0, horizon_days=7,
        verdict={"title": "客服工单自动化", "verdict": "pursue", "riskiest_assumption": "渠道能触达"},
        llm=MockBackend(responder),
        config={"user_template": "{title} 预测{target} 实际{actual} 裁决{verdict_tier} 假设{riskiest_assumption}"},
    )
    assert lesson == "渠道选错了,通用发帖转化率低"
    assert "客服工单自动化" in seen["user"]
    assert "pursue" in seen["user"]


def test_extract_lesson_llm_empty_on_failed_response():
    lesson = retro.extract_lesson_llm(
        "c1", "signups", 10.0, 3.0, 7, {},
        MockBackend(lambda req: LLMResponse(id=req.id, ok=False, error="boom")),
        {"user_template": "{title}"},
    )
    assert lesson == ""


def test_record_outcome_uses_llm_when_lesson_empty(tmp_path):
    # Log a verdict first so extract_lesson_llm has context to pull from.
    ledger.log_verdict(
        tmp_path, {"idea_id": "c1", "title": "客服工单自动化", "verdict": "pursue",
                   "riskiest_assumption": "渠道能触达"},
        actor="system",
    )

    def responder(req):
        return LLMResponse(id=req.id, ok=True, data={"lesson": "AI 提炼的教训"})

    out = retro.record_outcome(
        tmp_path, "c1", "2026-07-12", "signups", 3.0, target=10.0,
        llm=MockBackend(responder), llm_config={"user_template": "{title}"},
    )
    assert out.lesson == "AI 提炼的教训"


def test_record_outcome_founder_typed_lesson_wins_over_llm(tmp_path):
    def responder(req):
        raise AssertionError("LLM should never be called when --lesson is given")

    out = retro.record_outcome(
        tmp_path, "c1", "2026-07-12", "signups", 3.0, target=10.0,
        lesson="我自己写的教训", llm=MockBackend(responder), llm_config={"user_template": "{title}"},
    )
    assert out.lesson == "我自己写的教训"


def test_record_outcome_without_llm_stays_zero_token(tmp_path):
    out = retro.record_outcome(tmp_path, "c1", "2026-07-12", "signups", 3.0, target=10.0)
    assert out.lesson == ""
