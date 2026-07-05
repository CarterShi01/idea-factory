"""Tests for the pipeline-v2 additions to idea_core.models: Evidence, Outcome."""

from __future__ import annotations

from idea_core.models import (
    EVIDENCE_COMPETITOR_PRICING,
    EVIDENCE_PAYING_PROOF,
    Evidence,
    Outcome,
)


def test_evidence_roundtrip():
    ev = Evidence(
        id="ev1",
        candidate_id="c1",
        kind=EVIDENCE_PAYING_PROOF,
        source_url="https://example.com/jobs/123",
        source_date="2026-05-01",
        fetched_at="2026-07-05T10:00:00",
        summary="17 相关岗位,近30天,median ¥25k",
        numbers={"count": 17, "median_salary": 25000},
        valid=True,
    )
    d = ev.to_dict()
    assert d["kind"] == EVIDENCE_PAYING_PROOF
    back = Evidence.from_dict(d)
    assert back == ev


def test_evidence_stale_flag_is_caller_set():
    # valid is computed by idea_eval.enrich (24-month rule), not by the model itself.
    ev = Evidence(
        id="ev2", candidate_id="c1", kind=EVIDENCE_COMPETITOR_PRICING,
        source_url="https://example.com/pricing", source_date="2020-01-01", valid=False,
    )
    assert ev.valid is False


def test_outcome_roundtrip():
    out = Outcome(
        candidate_id="c1",
        tested_at="2026-07-12",
        prediction={"metric": "signups", "target": 10.0, "horizon_days": 7},
        actual={"metric": "signups", "value": 3.0},
        first_revenue=None,
        lesson="渠道选错了,应该发到人群更精准的社群。",
    )
    d = out.to_dict()
    back = Outcome.from_dict(d)
    assert back == out
    assert back.first_revenue is None
