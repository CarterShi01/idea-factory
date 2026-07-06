"""⑤enrich —— 给 rank 幸存者配齐"钱的证据链",过证据门(常开,fixture 支撑离线默认)。

三个 fetcher(竞品定价 / 招聘 / 成交)+ 一道证据门:≥1 付费证据 + ≥1 竞品定价 +
触达路径成立才算 ready。--live 才允许联网(live 版是需创始人批准的后续票,当前为桩)。
>24 月的证据抓回但 valid=False,不计入门,但仍给评审看("这条证据已过期")。
读:ideas.json  写:evidence.json(items=证据;extra.gate=每候选门结果)
只 import contract / runtime / factors。
"""

from __future__ import annotations

from idea_factory.contract import artifacts
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger

from .base import Fetcher, evidence_gate  # noqa: F401
from .run import default_fetchers, enrich_ideas, fetch_all  # noqa: F401


def run(ctx: StageContext) -> StageResult:
    ideas = artifacts.load_items(ctx.output_dir, "rank")
    evidence_by_id, gate_by_id = enrich_ideas(ideas, ctx.today, live=ctx.live)

    items = [ev.to_dict() for evs in evidence_by_id.values() for ev in evs]
    gate = {
        cid: {"ready": ready, "missing": missing}
        for cid, (ready, missing) in gate_by_id.items()
    }
    path = artifacts.save(
        ctx.output_dir, "enrich", items,
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
        extra={"gate": gate},
    )
    # 证据门不"杀"候选:缺证据的照样进 diligence,由 enforce_evidence_grounding
    # 压成 REVIEW(待补证据)。所以 impressions 全记 survived,门结果在 extra.gate。
    ready_ids = [cid for cid, g in gate.items() if g["ready"]]
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "enrich",
        survived_ids=[i.get("id", "") for i in ideas], killed={}, ts=ctx.today.isoformat(),
    )
    return StageResult(
        "enrich", entered=len(ideas), survived=len(ideas), killed=0,
        artifact=path, extra={"evidence_count": len(items), "gate_ready": len(ready_ids)},
    )
