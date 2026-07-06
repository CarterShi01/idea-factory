"""Tests for idea_eval.stats — pure read-side funnel/tier/prediction-error report."""

from __future__ import annotations

from idea_factory.runtime import ledger
from idea_factory.stages.retro import outcomes as retro, stats


def test_verdict_distribution_counts_system_verdicts_only(tmp_path):
    ledger.log_verdict(tmp_path, {"candidate_id": "a", "verdict": "pursue"}, actor="system")
    ledger.log_verdict(tmp_path, {"candidate_id": "a", "verdict": "review"}, actor="system")
    ledger.log_verdict(tmp_path, {"candidate_id": "a", "verdict": "review"}, actor="system")
    ledger.log_founder_action(tmp_path, "a", "star")  # no `verdict` field -> ignored

    dist = stats.verdict_distribution(tmp_path)
    assert dist == {"pursue": 1, "review": 2}


def test_funnel_report_aggregates_everything(tmp_path):
    ledger.log_impressions_bulk(
        tmp_path, "gen-1", "2026-W27", "triage_signal",
        survived_ids=["a", "b"], killed={"c": "stale_24m"}, ts="2026-07-05",
    )
    ledger.log_verdict(tmp_path, {"candidate_id": "a", "verdict": "kill"}, actor="system")
    retro.record_outcome(tmp_path, "a", "2026-07-12", "signups", 7.0, target=10.0, lesson="渠道不对")

    report = stats.funnel_report(tmp_path)
    assert report["stage_survival"]["triage_signal"]["survived"] == 2
    assert report["kill_reasons"] == {"stale_24m": 1}
    assert report["verdict_distribution"] == {"kill": 1}
    assert report["outcomes"]["count"] == 1
    assert report["outcomes"]["lessons"] == ["渠道不对"]


def test_format_report_handles_empty_ledger(tmp_path):
    text = stats.format_report(stats.funnel_report(tmp_path))
    assert "idea-eval stats" in text
    assert "暂无 ledger 数据" in text


def test_format_report_renders_nonempty_sections(tmp_path):
    ledger.log_impressions_bulk(
        tmp_path, "gen-1", "2026-W27", "triage_signal",
        survived_ids=["a"], killed={"b": "stale_24m"}, ts="2026-07-05",
    )
    ledger.log_verdict(tmp_path, {"candidate_id": "a", "verdict": "pursue"}, actor="system")
    text = stats.format_report(stats.funnel_report(tmp_path))
    assert "triage_signal: 存活 1 / 杀 1" in text
    assert "stale_24m: 1" in text
    assert "pursue: 1" in text
