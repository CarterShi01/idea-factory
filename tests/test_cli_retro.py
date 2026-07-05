"""Tests for the `idea-eval retro` CLI subcommand."""

from __future__ import annotations

from idea_core import ledger
from idea_eval.cli import main


def test_retro_subcommand_records_outcome(tmp_path, capsys):
    rc = main([
        "retro",
        "--data-dir", str(tmp_path),
        "--candidate", "c1",
        "--metric", "signups",
        "--actual", "7",
        "--target", "10",
        "--tested-at", "2026-07-12",
        "--lesson", "渠道选错了。",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "recorded outcome for c1" in out
    assert "prediction error" in out

    stored = ledger.read_outcomes(tmp_path)
    assert len(stored) == 1
    assert stored[0]["candidate_id"] == "c1"
    assert stored[0]["actual"]["value"] == 7.0


def test_retro_subcommand_default_tested_at(tmp_path):
    rc = main([
        "retro", "--data-dir", str(tmp_path), "--candidate", "c2",
        "--metric", "preorders", "--actual", "3",
    ])
    assert rc == 0
    stored = ledger.read_outcomes(tmp_path)
    assert stored[0]["tested_at"]  # some ISO date got filled in
