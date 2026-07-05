"""Tests for idea_eval.calibrate — read-only outcome-to-factor correlation.

Never writes to any config; only ever reports (or refuses to, below the sample
threshold).
"""

from __future__ import annotations

from idea_core import ledger
from idea_eval import calibrate, retro


def _log_verdict_with_factors(data_dir, idea_id, factors):
    ledger.log_verdict(data_dir, {"idea_id": idea_id, "title": idea_id, "factors": factors}, actor="system")


def test_insufficient_data_below_min_sample(tmp_path):
    _log_verdict_with_factors(tmp_path, "a", {"pain_intensity": 0.8})
    retro.record_outcome(tmp_path, "a", "2026-07-12", "signups", 12.0, target=10.0)

    report = calibrate.suggest_weights(tmp_path, min_sample=10)
    assert report["status"] == "insufficient_data"
    assert report["count"] == 1
    assert report["min_sample"] == 10
    assert "样本不足" in report["message"]


def test_ok_report_when_min_sample_satisfied(tmp_path):
    # Build 10 outcomes where pain_intensity tracks performance closely (strong
    # positive correlation) so the sign/magnitude is a meaningful sanity check.
    for i in range(10):
        pain = i / 9.0  # 0.0 .. 1.0
        target = 10.0
        actual = target * (0.5 + pain)  # higher pain_intensity -> better outcome
        _log_verdict_with_factors(tmp_path, f"c{i}", {"pain_intensity": pain, "build_cost": 0.5})
        retro.record_outcome(tmp_path, f"c{i}", "2026-07-12", "signups", actual, target=target)

    report = calibrate.suggest_weights(tmp_path, min_sample=10)
    assert report["status"] == "ok"
    assert report["count"] == 10
    assert report["correlations"]["pain_intensity"] > 0.9  # strong positive, by construction
    assert "build_cost" not in report["correlations"]  # constant factor -> zero variance -> excluded


def test_never_writes_any_file(tmp_path):
    before = set(tmp_path.rglob("*"))
    calibrate.suggest_weights(tmp_path, min_sample=1)
    after = set(tmp_path.rglob("*"))
    assert before == after  # read-only, zero side effects on an empty dir


def test_outcomes_without_target_or_factors_are_excluded(tmp_path):
    # no target -> prediction_error is None -> excluded
    retro.record_outcome(tmp_path, "no_target", "2026-07-12", "signups", 5.0)
    # target present but no verdict/factors logged for this candidate -> excluded
    retro.record_outcome(tmp_path, "no_factors", "2026-07-12", "signups", 5.0, target=10.0)

    report = calibrate.suggest_weights(tmp_path, min_sample=1)
    assert report["status"] == "insufficient_data"
    assert report["count"] == 0


def test_format_calibration_insufficient_data():
    report = {"status": "insufficient_data", "count": 2, "min_sample": 10, "message": "样本不足(...)"}
    text = calibrate.format_calibration(report)
    assert "样本不足" in text
    assert "2/10" in text


def test_format_calibration_ok():
    report = {
        "status": "ok", "count": 10,
        "correlations": {"pain_intensity": 0.95, "build_cost": -0.2},
        "message": "样本量足够...",
    }
    text = calibrate.format_calibration(report)
    assert "pain_intensity: +0.9500" in text
    assert "build_cost: -0.2000" in text
