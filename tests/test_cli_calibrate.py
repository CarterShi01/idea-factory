"""Tests for the `idea-eval calibrate` CLI subcommand."""

from __future__ import annotations

from idea_eval.cli import main


def test_calibrate_subcommand_reports_insufficient_data(tmp_path, capsys):
    rc = main(["calibrate", "--data-dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "idea-eval calibrate" in out
    assert "样本不足" in out


def test_calibrate_subcommand_respects_min_sample_flag(tmp_path, capsys):
    rc = main(["calibrate", "--data-dir", str(tmp_path), "--min-sample", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0/3" in out
