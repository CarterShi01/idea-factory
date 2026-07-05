"""Pipeline-level tests for idea_eval's opt-in require_evidence flag."""

from __future__ import annotations

import json
from datetime import date

from idea_core import ledger
from idea_core.llm import LLMResponse, MockBackend
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


def test_require_evidence_with_judge_sees_evidence_and_uncited_kill_is_demoted(tmp_path):
    """Full reorder check (#5): enrich runs BEFORE judge, so evidence_block is
    non-empty in the judge's prompt; a judge that kills WITHOUT citing any real
    evidence_id gets bounced to review by enforce_citation.
    """
    ideas_path = tmp_path / "processed" / "ideas.json"
    _write_ideas(ideas_path, [
        _idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
              factors=_STRONG_FACTORS, first_10_customers="HN 发帖"),
    ])
    seen_prompts = []

    def judge_responder(req):
        seen_prompts.append(req.user)
        return LLMResponse(
            id=req.id, ok=True,
            data={
                "verdict": "kill", "score": 20, "confidence": "high",
                "scores": {"pain_real": 0.2, "solo_buildable": 0.5, "reachable": 0.5, "defensible": 0.1, "timing": 0.5},
                "respond_to_critique": "", "killer_objection": "无护城河", "cheap_experiment": "",
                "reasons": [{"claim": "无护城河", "evidence_ids": []}],  # no citation despite real evidence
            },
        )

    result = run_evaluation(
        input_path=ideas_path, output_dir=tmp_path / "processed", today=REF_DATE,
        require_evidence=True, evidence_data_dir=tmp_path / "data", version=False,
        judge_backend="mock", critique=False, llm=MockBackend(judge_responder),
    )
    e = result.evaluations[0]
    assert e.judged_by == "llm"
    assert e.evidence, "evidence must have been fetched before the judge ran"
    assert any("钱的证据链" in p for p in seen_prompts), "judge prompt must include the evidence block"
    assert e.verdict == "review"
    assert e.citation_demoted is True

    # §6 M6: the judge's prompt+response must be logged to the ledger's trace
    # (single-idea trace view reads exactly this).
    trace_root = ledger.ledger_dir(tmp_path / "data") / "traces"
    run_dirs = list(trace_root.iterdir())
    assert len(run_dirs) == 1
    trace = ledger.read_trace(tmp_path / "data", run_dirs[0].name, "diligence")
    assert len(trace) == 1
    assert trace[0]["entity_id"] == "stripe1"
    assert "钱的证据链" in trace[0]["request"]["user"]
    assert trace[0]["response"]["data"]["verdict"] == "kill"


def test_persona_pressure_backend_attaches_objections_to_final_pursue_only(tmp_path):
    ideas_path = tmp_path / "processed" / "ideas.json"
    _write_ideas(ideas_path, [
        _idea("a", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账", factors=_STRONG_FACTORS),
        _idea("b", pain="蒙语母语者缺少语音助手", factors=_STRONG_FACTORS),
    ])

    def responder(req):
        return LLMResponse(id=req.id, ok=True, data={"objection": "我不会为这个付费"})

    pool = [{"persona": "测试人群", "domain": "test"}]
    result = run_evaluation(
        input_path=ideas_path, output_dir=tmp_path / "processed", today=REF_DATE, version=False,
        persona_pressure_backend="mock", persona_llm=MockBackend(responder),
    )
    # rule-only path: neither candidate reaches PURSUE on rule score alone in this
    # fixture, so the sub-step should be a no-op here — the real coverage of "only
    # touches final PURSUE" lives in test_persona_pressure.py's unit tests; this
    # test just confirms the pipeline wiring doesn't blow up end to end.
    assert result.evaluated == 2
    assert all(isinstance(e.persona_objections, list) for e in result.evaluations)
