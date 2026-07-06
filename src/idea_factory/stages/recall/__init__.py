"""①recall —— 从"钱在流动的地方"捞信号,宁滥勿缺。

读:data/raw/(离线夹具;--live 才允许联网通道抓取)
写:recall.json(归一化 Signal 全量)+ ledger impressions(stage="recall")
LLM:仅源③人群合成(backends["persona_sim"],默认关=静态人群)。
只 import contract / runtime / factors;绝不 import 兄弟段。
"""

from __future__ import annotations

from idea_factory.contract import artifacts
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger

from . import collect, normalize


def run(ctx: StageContext) -> StageResult:
    raw = collect.collect_all(
        ctx.data_dir,
        sources=ctx.sources,
        live=ctx.live,
        persona_llm=ctx.backends.get("persona_sim"),
    )
    signals = normalize.normalize(raw)
    path = artifacts.save(
        ctx.output_dir, "recall", [s.to_dict() for s in signals],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
        extra={"raw_count": len(raw)},
    )
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "recall",
        survived_ids=[s.id for s in signals], killed={}, ts=ctx.today.isoformat(),
    )
    return StageResult("recall", entered=len(raw), survived=len(signals), artifact=path)
