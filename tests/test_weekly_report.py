"""Tests for idea_eval.export.write_weekly_report — the §8-format weekly report."""

from __future__ import annotations

from idea_factory.contract.models import KILL, PURSUE, REVIEW, Evaluation
from idea_factory.stages.portfolio.report import write_weekly_report


def _idea(id_, **kw):
    base = {
        "id": id_, "source": "external_event", "observed_on": "2026-06-01",
        "pain": "痛点描述", "solution": "方案描述", "first_10_customers": "",
    }
    base.update(kw)
    return base


def test_weekly_report_shows_only_top_n_survivors(tmp_path):
    evals = [
        Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90),
        Evaluation(idea_id="b", title="B", verdict=REVIEW, eval_score=80),
        Evaluation(idea_id="c", title="C", verdict=REVIEW, eval_score=70),
        Evaluation(idea_id="d", title="D", verdict=KILL, eval_score=10),
    ]
    ideas_by_id = {e.idea_id: _idea(e.idea_id) for e in evals}
    path = tmp_path / "weekly_report.md"
    write_weekly_report(evals, ideas_by_id, path, week="2026-W27", top_n=2)

    text = path.read_text(encoding="utf-8")
    assert "本周 #1：A" in text
    assert "本周 #2：B" in text
    assert "C" not in text.split("本周 #2")[1]  # C excluded by top_n
    assert "D" not in text  # killed never shown


def test_weekly_report_tier_labels_and_evidence_gap_note(tmp_path):
    pursue = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90, evidence=[
        {"kind": "competitor_pricing", "source_url": "https://x.example.com", "summary": "S",
         "source_date": "2026-05-01", "valid": True, "numbers": {"price": 29, "currency": "USD"}},
    ])
    awaiting = Evaluation(
        idea_id="b", title="B", verdict=REVIEW, eval_score=50,
        evidence_missing=["paying_proof", "competitor_pricing"],
    )
    ideas_by_id = {"a": _idea("a"), "b": _idea("b")}
    path = tmp_path / "weekly_report.md"
    write_weekly_report([pursue, awaiting], ideas_by_id, path, week="2026-W27")

    text = path.read_text(encoding="utf-8")
    assert "tier: 本周就测" in text
    assert "tier: 待补证据" in text
    assert "https://x.example.com" in text
    assert "暂无证据" in text  # B has no evidence entries at all


def test_weekly_report_smoke_test_uses_first_10_customers_and_experiment_spec(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90, experiment={
        "metric": "preorders", "target": 10, "kill_below": 3,
        "horizon_days": 7, "budget_band": "0-500元",
    })
    idea = _idea("a", first_10_customers="在相关社群发帖招募")
    path = tmp_path / "weekly_report.md"
    write_weekly_report([e], {"a": idea}, path, week="2026-W27")

    text = path.read_text(encoding="utf-8")
    assert "在相关社群发帖招募" in text
    assert "preorders ≥ 10" in text
    assert "低于 3 判输" in text
    assert "idea retro" in text


def test_weekly_report_smoke_test_notes_missing_experiment_spec(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=REVIEW, eval_score=50)  # experiment left empty
    path = tmp_path / "weekly_report.md"
    write_weekly_report([e], {"a": _idea("a")}, path, week="2026-W27")

    text = path.read_text(encoding="utf-8")
    assert "暂无结构化实验规格" in text


def test_weekly_report_appends_calibrate_tail_when_ok(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)
    path = tmp_path / "weekly_report.md"
    report = {"status": "ok", "count": 12, "message": "样本量足够——…",
              "correlations": {"pain_intensity": 0.42, "build_cost": -0.1}}
    write_weekly_report([e], {"a": _idea("a")}, path, week="2026-W27", calibrate_report=report)

    text = path.read_text(encoding="utf-8")
    assert "因子校准" in text
    assert "pain_intensity: +0.4200" in text


def test_weekly_report_omits_calibrate_tail_when_insufficient(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)
    path = tmp_path / "weekly_report.md"
    report = {"status": "insufficient_data", "count": 2, "min_sample": 10, "message": "样本不足…"}
    write_weekly_report([e], {"a": _idea("a")}, path, week="2026-W27", calibrate_report=report)

    text = path.read_text(encoding="utf-8")
    assert "因子校准" not in text


def test_weekly_report_omits_calibrate_tail_when_none(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)
    path = tmp_path / "weekly_report.md"
    write_weekly_report([e], {"a": _idea("a")}, path, week="2026-W27")  # calibrate_report defaults None

    text = path.read_text(encoding="utf-8")
    assert "因子校准" not in text


def test_weekly_report_renders_persona_objections(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90, persona_objections=[
        {"persona": "蒙语母语中老年人", "objection": "我不识字看不懂这个界面"},
    ])
    path = tmp_path / "weekly_report.md"
    write_weekly_report([e], {"a": _idea("a")}, path, week="2026-W27")

    text = path.read_text(encoding="utf-8")
    assert "人群反对声" in text
    assert "蒙语母语中老年人：我不识字看不懂这个界面" in text
