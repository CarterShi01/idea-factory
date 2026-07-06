"""②triage —— 便宜地硬杀,省下后面所有钱(常开,不再是 opt-in 旗)。

红线按序:精确/词法近重去重(.dedup)→ >24 月过期(.rules)。use_state 时先走
SeenStore 跨日去重 + 趋势回填(runtime.state / runtime.trends)。
读:recall.json  写:triage.json(幸存 Signal;killed 清单进 extra 供误杀审计)
LLM:无(零 token)。只 import contract / runtime / factors。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from idea_factory.contract import artifacts
from idea_factory.contract.models import Signal
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger

from . import dedup, rules

NEAR_DUP = "exact_or_near_dup"
SEEN_BEFORE = "seen_before"


def _dynamic_dedup_and_trends(signals: list[Signal], state_dir: Path, today: date):
    """动态模式:SeenStore 跨日去重 + SignalHistory 趋势,把 trend_status/growth_speed 回填到信号。"""
    from idea_factory.runtime.state import SeenStore, SignalHistory
    from idea_factory.runtime.trends import classify

    today_iso = today.isoformat()
    seen = SeenStore.load(state_dir / "seen.jsonl")
    hist = SignalHistory.load(state_dir / "signal_history.jsonl")

    # 历史记录所有信号的话题(含已见过的,以追踪持续升温);只保留"新"信号
    for s in signals:
        hist.add(s.topic, s.observed_on or today_iso)
    fresh = [s for s in signals if seen.observe(s.dedup_key, today_iso)]
    seen_dropped = [s for s in signals if s not in fresh]
    # 批内再做一次词法近重去重
    fresh, dup_dropped = dedup.dedupe_signals(fresh)
    # 趋势分类 → 回填
    for s in fresh:
        status, speed = classify(hist.series(s.topic, window=30, end=today_iso))
        s.trend_status, s.growth_speed = status, speed

    seen.save()
    hist.save()
    killed = {s.id: SEEN_BEFORE for s in seen_dropped}
    killed.update({s.id: NEAR_DUP for s in dup_dropped})
    return fresh, killed


def run(ctx: StageContext) -> StageResult:
    items = artifacts.load_items(ctx.output_dir, "recall")
    signals = [Signal.from_dict(d) for d in items]

    if ctx.use_state:
        kept, killed = _dynamic_dedup_and_trends(signals, Path(ctx.data_dir) / "state", ctx.today)
    else:
        kept, dropped = dedup.dedupe_signals(signals)
        killed = {s.id: NEAR_DUP for s in dropped}

    kept, stale_killed = rules.triage_signals(kept, ctx.today)
    killed.update(stale_killed)

    path = artifacts.save(
        ctx.output_dir, "triage", [s.to_dict() for s in kept],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
        extra={"killed": killed},
    )
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "triage",
        survived_ids=[s.id for s in kept], killed=killed, ts=ctx.today.isoformat(),
    )
    return StageResult("triage", entered=len(signals), survived=len(kept), killed=len(killed), artifact=path)
