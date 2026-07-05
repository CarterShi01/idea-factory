"""Pipeline-level tests for idea_eval's opt-in require_evidence flag."""

from __future__ import annotations

import json
from datetime import date

from idea_core import ledger
from idea_eval.pipeline import run_evaluation

REF_DATE = date(2026, 7, 5)


def _write_ideas(path, ideas):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ideas, ensure_ascii=False), encoding="utf-8")


def _idea(id_, *, pain, factors, first_10_customers=""):
    return {
        "id": id_, "signal_id": "s1", "source": "external_event", "title": id_,
        "pain": pain, "solution": "工具", "target_user": "开发者", "observed_on": "2026-06-01",
        "confidence": "real", "first_10_customers": first_10_customers,
        "factors": factors, "alpha": 0.5, "decay": 1.0,
    }


_STRONG_FACTORS = {
    "pain_intensity": 0.7, "payment_signal": 0.7, "build_cost": 0.8,
    "distribution_fit": 0.6, "market_freshness": 0.5, "competition_density": 0.6,
    "moat_signal": 0.5, "founder_fit": 0.6,
}


def test_require_evidence_demotes_ungrounded_pursue_and_logs_ledger(tmp_path):
    ideas_path = tmp_path / "processed" / "ideas.json"
    _write_ideas(ideas_path, [
        _idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
              factors=_STRONG_FACTORS, first_10_customers="HN 发帖"),
        _idea("mongolian1", pain="蒙语母语者缺少语音助手", factors=_STRONG_FACTORS),
    ])

    result = run_evaluation(
        input_path=ideas_path,
        output_dir=tmp_path / "processed",
        today=REF_DATE,
        require_evidence=True,
        evidence_data_dir=tmp_path / "data",
        version=False,
    )
    by_id = {e.idea_id: e for e in result.evaluations}
    assert by_id["stripe1"].evidence_ready is True
    assert by_id["mongolian1"].evidence_ready is False
    # mongolian1 would otherwise pursue/review on rule score alone, but with no
    # evidence at all it must never land on PURSUE.
    assert by_id["mongolian1"].verdict != "pursue"

    rates = ledger.channel_survival_rates(tmp_path / "data", stage="diligence")
    assert "diligence" in rates
    verdicts_log = ledger.read_jsonl(ledger.ledger_dir(tmp_path / "data") / ledger.VERDICTS)
    assert len(verdicts_log) == 2


def test_require_evidence_off_by_default_no_ledger_written(tmp_path):
    ideas_path = tmp_path / "processed" / "ideas.json"
    _write_ideas(ideas_path, [_idea("a", pain="p", factors=_STRONG_FACTORS)])
    result = run_evaluation(
        input_path=ideas_path, output_dir=tmp_path / "processed", today=REF_DATE, version=False,
    )
    assert result.evaluated == 1
    assert not (tmp_path / "data" / "ledger").exists()
    assert result.weekly_report_path is None


def test_require_evidence_writes_weekly_report(tmp_path):
    ideas_path = tmp_path / "processed" / "ideas.json"
    _write_ideas(ideas_path, [
        _idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
              factors=_STRONG_FACTORS, first_10_customers="HN 发帖"),
    ])
    result = run_evaluation(
        input_path=ideas_path, output_dir=tmp_path / "processed", today=REF_DATE,
        require_evidence=True, evidence_data_dir=tmp_path / "data", version=False,
    )
    assert result.weekly_report_path is not None
    assert result.weekly_report_path.exists()
    text = result.weekly_report_path.read_text(encoding="utf-8")
    assert "本周候选" in text
