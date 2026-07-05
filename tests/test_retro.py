"""Tests for idea_eval.retro — outcome recording + aggregation."""

from __future__ import annotations

from idea_core import ledger
from idea_eval import retro


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
