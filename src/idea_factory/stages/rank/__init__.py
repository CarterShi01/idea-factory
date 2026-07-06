"""④rank —— 纯代码因子加权,决定谁配进昂贵半场(零 token)。

打分(.score:分桶权重 × 时间衰减 × commodity 硬罚)→ MMR 重排 → 粗排切分
coarse_k → ideas.json(便宜/昂贵缝,保留历史文件名);人看的 ideas.md 摘要再做
一次硬去聚类(.select / .export)。
读:candidates.json  写:ideas.json + ideas.md + ledger impressions(stage="rank")
只 import contract / runtime / factors。
"""

from __future__ import annotations

from pathlib import Path

from idea_factory.contract import artifacts
from idea_factory.contract.models import IdeaCandidate
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger
from idea_factory.runtime.config import load_funnel

from . import export, score as score_mod, select

RANKED_OUT = "ranked_out"


def run(ctx: StageContext) -> StageResult:
    candidates = [IdeaCandidate.from_dict(d) for d in artifacts.load_items(ctx.output_dir, "generate")]

    funnel = load_funnel()
    coarse_k = int((funnel.get("cut_sizes", {}) or {}).get("coarse_k", 50))

    scored = score_mod.score(candidates, today=ctx.today)
    ranked = select.rank(scored)
    coarse = select.coarse_select(ranked, coarse_k)
    digest = select.select_diverse_top_n(coarse, n=ctx.top_n)

    kept_ids = {s.candidate.id for s in coarse}
    killed = {s.candidate.id: RANKED_OUT for s in ranked if s.candidate.id not in kept_ids}

    path = artifacts.save(
        ctx.output_dir, "rank", [s.to_dict() for s in coarse],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
    )
    export.write_markdown(digest, Path(ctx.output_dir) / "ideas.md", today=ctx.today, top_n=ctx.top_n)
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "rank",
        survived_ids=sorted(kept_ids), killed=killed, ts=ctx.today.isoformat(),
    )
    return StageResult(
        "rank", entered=len(candidates), survived=len(coarse), killed=len(killed),
        artifact=path, extra={"markdown": str(Path(ctx.output_dir) / "ideas.md")},
    )
