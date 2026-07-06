"""idea_eval.stats -- pure read-side reporting over the ledger.

Per ``docs/design/pipeline-v2-plan.md`` §5/§6 (M5): no LLM, no side effects --
every number here is computed from ``data/ledger/*.jsonl``, already written by
``idea_gen``'s opt-in triage stage and ``idea_eval``'s opt-in
``require_evidence`` diligence stage. This is the funnel view's data source
(and, later, Studio's).
"""

from __future__ import annotations

from pathlib import Path

from idea_factory.runtime import ledger

from . import outcomes as retro


def verdict_distribution(data_dir: str | Path) -> dict[str, int]:
    """Count of each verdict tier across all logged verdicts (verdicts.jsonl).

    Only counts system-authored verdict records (skips ``founder_*`` label
    events, which don't carry a ``verdict`` field).
    """
    counts: dict[str, int] = {}
    for rec in ledger.read_jsonl(ledger.ledger_dir(data_dir) / ledger.VERDICTS):
        v = rec.get("verdict")
        if v:
            counts[v] = counts.get(v, 0) + 1
    return counts


def funnel_report(data_dir: str | Path) -> dict:
    """Full report: per-stage survival, kill reasons, verdict distribution, outcomes."""
    return {
        "stage_survival": ledger.channel_survival_rates(data_dir),
        "kill_reasons": ledger.killed_by_breakdown(data_dir),
        "verdict_distribution": verdict_distribution(data_dir),
        "outcomes": retro.summarize_outcomes(data_dir),
    }


def format_report(report: dict) -> str:
    lines: list[str] = ["# idea-eval stats", ""]

    lines.append("## 漏斗各段存活率")
    if not report["stage_survival"]:
        lines.append("(暂无 ledger 数据 —— 用 idea-gen --use-triage / idea-eval --require-evidence 跑一次)")
    for stage, s in report["stage_survival"].items():
        lines.append(f"- {stage}: 存活 {s['survived']} / 杀 {s['killed']} (存活率 {s['rate']:.0%})")
    lines.append("")

    lines.append("## 杀因分布")
    if not report["kill_reasons"]:
        lines.append("(无)")
    for reason, n in sorted(report["kill_reasons"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- {reason}: {n}")
    lines.append("")

    lines.append("## 裁决分布")
    if not report["verdict_distribution"]:
        lines.append("(无)")
    for verdict, n in sorted(report["verdict_distribution"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- {verdict}: {n}")
    lines.append("")

    lines.append("## 预测 vs 实际(retro)")
    o = report["outcomes"]
    lines.append(f"- 已记录结果: {o['count']}")
    if o["avg_prediction_error"] is not None:
        lines.append(f"- 平均预测误差: {o['avg_prediction_error']:+.1%}")
    lines.append(f"- 已产生首笔收入事件: {o['first_revenue_events']}")
    for lesson in o["lessons"]:
        lines.append(f"  · {lesson}")

    return "\n".join(lines)
