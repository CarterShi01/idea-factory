"""Tests for the `idea-eval stats` CLI subcommand."""

from __future__ import annotations

from idea_factory.runtime import ledger
from idea_factory.cli import main


def test_stats_subcommand_prints_report(tmp_path, capsys):
    ledger.log_impressions_bulk(
        tmp_path, "gen-1", "2026-W27", "triage_signal",
        survived_ids=["a"], killed={"b": "stale_24m"}, ts="2026-07-05",
    )
    rc = main(["stats", "--data-dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "idea-eval stats" in out
    assert "stale_24m" in out
