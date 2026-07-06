"""⑦portfolio —— 组合出口:打散成一个组合,写周报 + 决策备忘(纯代码,零 token)。

打散(.diversify:来源桶配额中文为主 + 创始人边单边上限 + 近重去聚类)选出终端
UI_N 组合排到头部;报告(.report)写 decision_memos.md(日常)+ weekly_report.md
(北极星工件,每条带证据链 + 48h 测试包)。最后 versioning 快照本次 run。
读:verdicts.json + ideas.json  写:screened.json + decision_memos.md + weekly_report.md
只 import contract / runtime / factors。
"""

from __future__ import annotations

from pathlib import Path

from idea_factory.contract import artifacts
from idea_factory.contract.models import KILL, PURSUE, REVIEW, Evaluation
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger, versioning

from . import diversify, report


def run(ctx: StageContext) -> StageResult:
    evaluations = [Evaluation.from_dict(d) for d in artifacts.load_items(ctx.output_dir, "diligence")]
    ideas_by_id = {i.get("id", ""): i for i in artifacts.load_items(ctx.output_dir, "rank")}

    evaluations = diversify.diversify_select(evaluations, ideas_by_id)

    out = Path(ctx.output_dir)
    path = artifacts.save(
        ctx.output_dir, "portfolio", [e.to_dict() for e in evaluations],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
    )
    memos_path = out / "decision_memos.md"
    report.write_memos(evaluations, memos_path, today=ctx.today, top_n=ctx.top_n)
    weekly_path = out / "weekly_report.md"
    report.write_weekly_report(
        evaluations, ideas_by_id, weekly_path,
        week=ctx.week or ledger.week_of(ctx.today.isoformat()), top_n=ctx.weekly_top_n,
    )

    version_id = versioning.commit_version(ctx.output_dir, ctx.today.isoformat()) if ctx.version else None

    counts = {
        "pursue": sum(1 for e in evaluations if e.verdict == PURSUE),
        "review": sum(1 for e in evaluations if e.verdict == REVIEW),
        "killed": sum(1 for e in evaluations if e.verdict == KILL),
    }
    return StageResult(
        "portfolio", entered=len(evaluations), survived=counts["pursue"] + counts["review"],
        killed=counts["killed"], artifact=path,
        extra={
            "memos": str(memos_path), "weekly_report": str(weekly_path),
            "version_id": version_id, **counts,
        },
    )
