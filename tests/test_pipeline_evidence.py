"""Pipeline-level tests for the evidence gate + citation discipline (enrich→diligence)."""

from __future__ import annotations

from datetime import date

from idea_factory import pipeline
from idea_factory.contract import artifacts
from idea_factory.contract.models import Evaluation
from idea_factory.runtime import ledger
from idea_factory.runtime.llm import LLMResponse, MockBackend

REF_DATE = date(2026, 7, 5)


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


def _seed_rank_artifact(output_dir, ideas):
    artifacts.save(output_dir, "rank", ideas, run_id="run-test-1", week="2026-W27", today=REF_DATE)


def _run_expensive(tmp_path, ideas, to_stage="diligence", **kw):
    output_dir = tmp_path / "processed"
    _seed_rank_artifact(output_dir, ideas)
    res = pipeline.run(
        data_dir=tmp_path / "data", output_dir=output_dir, today=REF_DATE,
        from_stage="enrich", to_stage=to_stage, version=False, **kw,
    )
    evals = [Evaluation.from_dict(d) for d in artifacts.load_items(output_dir, "diligence")]
    return res, evals


def test_evidence_gate_demotes_ungrounded_pursue_and_logs_ledger(tmp_path):
    _, evals = _run_expensive(tmp_path, [
        _idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
              factors=_STRONG_FACTORS, first_10_customers="HN 发帖"),
        _idea("mongolian1", pain="蒙语母语者缺少语音助手", factors=_STRONG_FACTORS),
    ])
    by_id = {e.idea_id: e for e in evals}
    assert by_id["stripe1"].evidence_ready is True
    assert by_id["mongolian1"].evidence_ready is False
    # mongolian1 would otherwise pursue/review on rule score alone, but with no
    # evidence at all it must never land on PURSUE.
    assert by_id["mongolian1"].verdict != "pursue"

    rates = ledger.channel_survival_rates(tmp_path / "data", stage="diligence")
    assert "diligence" in rates
    verdicts_log = ledger.read_jsonl(ledger.ledger_dir(tmp_path / "data") / ledger.VERDICTS)
    assert len(verdicts_log) == 2


def test_run_continues_run_id_from_input_artifact(tmp_path):
    # --from 续跑必须继承上游工件的 run_id(同一条 run 线)。
    res, _ = _run_expensive(tmp_path, [_idea("a", pain="p", factors=_STRONG_FACTORS)])
    assert res.run_id == "run-test-1"
    env = artifacts.load(tmp_path / "processed", "diligence")
    assert env["run_id"] == "run-test-1"


def test_portfolio_writes_weekly_report(tmp_path):
    _run_expensive(tmp_path, [
        _idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
              factors=_STRONG_FACTORS, first_10_customers="HN 发帖"),
    ], to_stage="portfolio")
    weekly = tmp_path / "processed" / "weekly_report.md"
    assert weekly.exists()
    assert "本周候选" in weekly.read_text(encoding="utf-8")


def test_weekly_report_calibrate_tail_reflects_real_outcome_sample_size(tmp_path):
    """pipeline.py wires ctx.calibrate_report (agent-service-plan.md §B3) without
    breaking the stages/portfolio<->stages/retro isolation rule -- verified
    end-to-end via the actual rendered file, not by reaching into ctx.
    """
    from idea_factory.stages.retro import outcomes as retro_outcomes

    # Vary pain_intensity per idea -- calibrate's Pearson correlation is undefined
    # (None) when a factor has zero variance across the sample, so identical
    # factors for all 10 would silently render the message with no factor lines.
    ideas = [
        _idea(f"i{n}", pain="p", factors={**_STRONG_FACTORS, "pain_intensity": 0.1 * (n + 1)})
        for n in range(10)
    ]
    _run_expensive(tmp_path, ideas, to_stage="diligence")  # populates verdicts.jsonl (factors logged)

    data_dir = tmp_path / "data"
    weekly = tmp_path / "processed" / "weekly_report.md"

    # Below min_sample (0 outcomes so far): rerunning portfolio alone must not show the tail.
    pipeline.run(data_dir=data_dir, output_dir=tmp_path / "processed", today=REF_DATE,
                 only="portfolio", version=False)
    assert "因子校准" not in weekly.read_text(encoding="utf-8")

    # Seed >= DEFAULT_MIN_SAMPLE (10) real outcomes matching the logged candidates,
    # actual value varying too so both series have nonzero variance.
    for n in range(10):
        retro_outcomes.record_outcome(
            data_dir, f"i{n}", "2026-07-12", "signups", float(n + 1), target=10.0,
        )

    pipeline.run(data_dir=data_dir, output_dir=tmp_path / "processed", today=REF_DATE,
                 only="portfolio", version=False)
    text = weekly.read_text(encoding="utf-8")
    assert "因子校准" in text
    assert "pain_intensity" in text.split("因子校准")[1]


def test_judge_sees_evidence_and_uncited_kill_is_demoted(tmp_path):
    """enrich runs BEFORE judge, so evidence_block is non-empty in the judge's
    prompt; a judge that kills WITHOUT citing any real evidence_id gets bounced
    to review by enforce_citation.
    """
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

    _, evals = _run_expensive(
        tmp_path,
        [_idea("stripe1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
               factors=_STRONG_FACTORS, first_10_customers="HN 发帖")],
        judge_backend="mock", critique=False,
        backends={"judge": MockBackend(judge_responder)},
    )
    e = evals[0]
    assert e.judged_by == "llm"
    assert e.evidence, "evidence must have been fetched before the judge ran"
    assert any("钱的证据链" in p for p in seen_prompts), "judge prompt must include the evidence block"
    assert e.verdict == "review"
    assert e.citation_demoted is True

    # the judge's prompt+response must be logged to the ledger's trace
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
    def responder(req):
        return LLMResponse(id=req.id, ok=True, data={"objection": "我不会为这个付费"})

    _, evals = _run_expensive(
        tmp_path,
        [
            _idea("a", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账", factors=_STRONG_FACTORS),
            _idea("b", pain="蒙语母语者缺少语音助手", factors=_STRONG_FACTORS),
        ],
        persona_pressure_backend="mock",
        backends={"persona_pressure": MockBackend(responder)},
    )
    # rule-only path: neither candidate reaches PURSUE on rule score alone in this
    # fixture, so the sub-step should be a no-op here — the real coverage of "only
    # touches final PURSUE" lives in test_persona_pressure.py's unit tests; this
    # test just confirms the pipeline wiring doesn't blow up end to end.
    assert len(evals) == 2
    assert all(isinstance(e.persona_objections, list) for e in evals)
