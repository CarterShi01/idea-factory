"""Tests for idea_core.ledger — the three append-only logs + trace."""

from __future__ import annotations

from idea_factory.runtime import ledger


def test_next_run_id_increments_per_day(tmp_path):
    r1 = ledger.next_run_id(tmp_path, "2026-07-05", kind="gen")
    assert r1 == "gen-2026-07-05-1"
    ledger.log_impression(tmp_path, r1, "2026-W27", "recall", "s1", ledger.SURVIVED, ts="2026-07-05")

    r2 = ledger.next_run_id(tmp_path, "2026-07-05", kind="gen")
    assert r2 == "gen-2026-07-05-2"

    r_next_day = ledger.next_run_id(tmp_path, "2026-07-06", kind="gen")
    assert r_next_day == "gen-2026-07-06-1"


def test_log_impressions_bulk_and_survival_rates(tmp_path):
    run_id = "gen-2026-07-05-1"
    ledger.log_impressions_bulk(
        tmp_path, run_id, "2026-W27", "triage",
        survived_ids=["a", "b", "c"],
        killed={"d": "stale_24m", "e": "profile_mismatch", "f": "stale_24m"},
        ts="2026-07-05",
    )
    rates = ledger.channel_survival_rates(tmp_path, stage="triage")
    assert rates["triage"]["survived"] == 3
    assert rates["triage"]["killed"] == 3
    assert rates["triage"]["rate"] == 0.5

    breakdown = ledger.killed_by_breakdown(tmp_path, stage="triage")
    assert breakdown == {"stale_24m": 2, "profile_mismatch": 1}


def test_verdicts_and_founder_action(tmp_path):
    ledger.log_verdict(tmp_path, {"candidate_id": "x1", "tier": "test_now"}, actor="system", ts="2026-07-05")
    ledger.log_founder_action(tmp_path, "x1", "star", ts="2026-07-05")

    records = ledger.read_jsonl(ledger.ledger_dir(tmp_path) / ledger.VERDICTS)
    assert len(records) == 2
    assert records[0]["actor"] == "system"
    assert records[1]["event"] == "founder_star"
    assert records[1]["actor"] == "founder"


def test_outcomes_roundtrip(tmp_path):
    outcome = ledger.Outcome(
        candidate_id="x1",
        tested_at="2026-07-12",
        prediction={"metric": "signups", "target": 10.0, "horizon_days": 7},
        actual={"metric": "signups", "value": 7.0},
        first_revenue=None,
        lesson="预测偏乐观,渠道转化比预期低。",
    )
    ledger.log_outcome(tmp_path, outcome)
    outcomes = ledger.read_outcomes(tmp_path)
    assert len(outcomes) == 1
    assert outcomes[0]["candidate_id"] == "x1"
    assert outcomes[0]["actual"]["value"] == 7.0


def test_trace_roundtrip(tmp_path):
    ledger.log_trace(
        tmp_path, "eval-2026-07-05-1", "diligence", "x1",
        prompt_version="diligence_judge@v1",
        request={"user": "..."}, response={"tier": "test_now"},
        model="tc-code", ts="2026-07-05",
    )
    trace = ledger.read_trace(tmp_path, "eval-2026-07-05-1", "diligence")
    assert len(trace) == 1
    assert trace[0]["entity_id"] == "x1"
    assert trace[0]["prompt_version"] == "diligence_judge@v1"


def test_week_of():
    assert ledger.week_of("2026-07-05") == "2026-W27"
    assert ledger.week_of("not-a-date") == "not-a-date"


def test_reads_tolerate_missing_or_bad_lines(tmp_path):
    assert ledger.read_jsonl(tmp_path / "nope.jsonl") == []
    p = tmp_path / "bad.jsonl"
    p.write_text("{\"a\":1}\nnot json\n{\"b\":2}\n", encoding="utf-8")
    assert ledger.read_jsonl(p) == [{"a": 1}, {"b": 2}]
