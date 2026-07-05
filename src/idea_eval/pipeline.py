"""idea_eval pipeline -- read idea_gen's candidates, screen them, write results.

    ideas.json (from idea_gen)  ->  evaluate (kill-gate + rubric)  ->  screened.json + decision_memos.md

idea_eval depends only on its own modules and ``idea_core``; it never imports
``idea_gen``. The two halves talk through the ``ideas.json`` file on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idea_core.llm import LLMBackend, get_backend, load_step_config
from idea_core import ledger, versioning

from . import evaluate, export
from .evaluate import KILL, PURSUE, REVIEW


def _llm_backend(name: str, today: date, job_dir: str | Path, step: str = "judge") -> LLMBackend:
    """Build an LLM backend; CC-handoff gets a dated, step-scoped job name.

    ``step`` separates the critique pack from the judge pack so a CC-handoff run
    becomes two distinct manual fulfilments (critique-<date>, then judge-<date>).
    """
    if name == "cc":
        return get_backend("cc", job_dir=job_dir, job_name=f"{step}-{today.isoformat()}")
    if name == "dify":
        return get_backend("dify", step=step)  # per-step Dify app/key; prompt lives in the flow
    return get_backend(name)


@dataclass
class EvalResult:
    evaluated: int = 0
    pursue: int = 0
    review: int = 0
    killed: int = 0
    evaluations: list = field(default_factory=list)
    json_path: Path | None = None
    memos_path: Path | None = None
    version_id: str | None = None
    weekly_report_path: Path | None = None  # only set when require_evidence=True


def run_evaluation(
    input_path: str | Path = "data/processed/ideas.json",
    output_dir: str | Path = "data/processed",
    today: date | None = None,
    floor: float = evaluate.DEFAULT_FLOOR,
    top_n: int = 20,
    judge_backend: str = "none",
    critique: bool = True,
    llm: LLMBackend | None = None,
    critique_llm: LLMBackend | None = None,
    job_dir: str | Path = "data/llm_jobs",
    version: bool = True,
    require_evidence: bool = False,
    evidence_data_dir: str | Path = "data",
    evidence_live: bool = False,
    max_pursue_frac: float = evaluate.DEFAULT_MAX_PURSUE_FRAC,
    weekly_top_n: int = 3,
) -> EvalResult:
    """Screen idea_gen's candidates.

    ``judge_backend``: ``"none"`` (rule-only, offline default, zero token) or an
    LLM backend name (``"router"`` / ``"cc"`` / ``"mock"``). When set, the rule
    kill-gate runs first and the LLM judge (B) only sees the survivors (Top-K),
    using ``config/llm/judge.json``.

    ``critique``: when True (default) and ``judge_backend != "none"``, runs an
    adversarial devil's advocate pass over the rule-survivors *before* the judge,
    using ``config/llm/critique.json``. The critique output is injected into the
    judge prompt; the judge must respond to it (anti-self-enhancement). Disable
    with False to skip critique (token-thrifty or for calibration A/B).

    ``llm`` / ``critique_llm``: optional pre-built backends (test seam). When
    only ``llm`` is given, it is also used for critique.

    ``require_evidence`` (docs/design/pipeline-v2-plan.md §5④⑤, opt-in, default
    off so the existing rule/critique/judge path is byte-for-byte unchanged
    unless a caller asks): runs ``idea_eval.enrich`` over the rule-survivors,
    attaches the evidence + gate to each :class:`evaluate.Evaluation`, demotes
    any ungrounded PURSUE to REVIEW (``enforce_evidence_grounding``), then caps
    the batch's PURSUE fraction (``enforce_forced_distribution``,
    ``max_pursue_frac``). Also logs every verdict + this stage's
    survived/killed counts to ``evidence_data_dir/ledger`` for the funnel view.
    ``evidence_live`` mirrors ``idea_gen``'s ``live`` flag but for enrich's
    fetchers -- currently a stubbed no-op (see ``idea_eval.enrich``).
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    today = today or date.today()

    ideas = json.loads(input_path.read_text(encoding="utf-8"))
    ideas_by_id = {i.get("id", ""): i for i in ideas}
    evaluations = evaluate.evaluate_all(ideas, floor=floor)

    if judge_backend != "none":
        if critique:
            crit_backend = critique_llm or llm or _llm_backend(
                judge_backend, today, job_dir, step="critique"
            )
            evaluate.critique_survivors(
                evaluations, ideas_by_id, crit_backend, load_step_config("critique")
            )
        judge_be = llm or _llm_backend(judge_backend, today, job_dir, step="judge")
        evaluations = evaluate.judge_survivors(
            evaluations, ideas_by_id, judge_be, load_step_config("judge")
        )

    # 漏斗第 5-6 层(尽调取证 + 强制分布):证据门 + 反-整批待验证纪律。opt-in,不改
    # 现有 rule/critique/judge 路径的默认行为。
    if require_evidence:
        from . import enrich

        evidence_by_id, gate_by_id = enrich.enrich_ideas(ideas, today, live=evidence_live)
        evaluate.apply_evidence(evaluations, evidence_by_id, gate_by_id)
        evaluations = evaluate.enforce_evidence_grounding(evaluations)
        evaluations = evaluate.enforce_forced_distribution(evaluations, max_pursue_frac=max_pursue_frac)

        week = ledger.week_of(today.isoformat())
        run_id = ledger.next_run_id(evidence_data_dir, today.isoformat(), kind="eval")
        survived = [e.idea_id for e in evaluations if e.verdict != KILL]
        killed_map = {e.idea_id: (e.killed_by[0] if e.killed_by else "eval_kill") for e in evaluations if e.verdict == KILL}
        ledger.log_impressions_bulk(
            evidence_data_dir, run_id, week, "diligence",
            survived_ids=survived, killed=killed_map, ts=today.isoformat(),
        )
        for e in evaluations:
            ledger.log_verdict(evidence_data_dir, e.to_dict(), actor="system", ts=today.isoformat())

    # 漏斗第 4 层 打散:把精排幸存者按 来源配额(中文为主)+ 单边上限 + 去聚类 选出终端组合,
    # 排到头部(WebUI/top3 读头部即得多样化的 UI_N)。不改判决,只改顺序。
    evaluations = evaluate.diversify_select(evaluations, ideas_by_id)

    json_path = output_dir / "screened.json"
    memos_path = output_dir / "decision_memos.md"
    export.write_json(evaluations, json_path)
    export.write_memos(evaluations, memos_path, today=today, top_n=top_n)

    # 漏斗第 7 层(组合出口):周报只在证据门跑过时才有意义(否则全体待补证据),
    # 排在打散之后所以头部顺序与 screened.json/decision_memos.md 一致。
    weekly_report_path = None
    if require_evidence:
        weekly_report_path = output_dir / "weekly_report.md"
        export.write_weekly_report(
            evaluations, ideas_by_id, weekly_report_path,
            week=ledger.week_of(today.isoformat()), top_n=weekly_top_n,
        )

    # Snapshot this run as an immutable version (offline, stdlib) unless opted out.
    # Version id is deterministic on ``today`` (Nth run of that date).
    version_id = versioning.commit_version(output_dir, today.isoformat()) if version else None

    return EvalResult(
        evaluated=len(evaluations),
        pursue=sum(1 for e in evaluations if e.verdict == PURSUE),
        review=sum(1 for e in evaluations if e.verdict == REVIEW),
        killed=sum(1 for e in evaluations if e.verdict == KILL),
        evaluations=evaluations,
        json_path=json_path,
        memos_path=memos_path,
        version_id=version_id,
        weekly_report_path=weekly_report_path,
    )
