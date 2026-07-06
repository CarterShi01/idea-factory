"""③generate —— 幸存信号 → 成型候选(具体机制,禁模板套话);过量生产,质量闸在下游。

后端:rule(离线零 token,CI/夹具)| LLM(.llm:per-source 分叉 + 跨源融合,单次 batch)。
候选侧红线:显式 anti-fit(factors.has_hard_anti_fit,创始人画像明确不适合的方向)就地杀。
读:triage.json  写:candidates.json + ledger impressions(stage="generate")
只 import contract / runtime / factors。可能抛 PendingHandoff(CC-handoff),由 CLI 接。
"""

from __future__ import annotations

from idea_factory.contract import artifacts
from idea_factory.contract.models import IdeaCandidate, Signal
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.factors import has_hard_anti_fit
from idea_factory.runtime import ledger
from idea_factory.runtime.llm import load_step_config

from . import llm as llm_mod
from . import rule

ANTI_FIT = "profile_mismatch"


def _screen_anti_fit(candidates: list[IdeaCandidate]) -> tuple[list[IdeaCandidate], dict[str, str]]:
    """候选侧硬红线:创始人画像显式 anti-fit 的方向直接杀(原 idea_gen.triage.triage_candidates)。"""
    kept: list[IdeaCandidate] = []
    killed: dict[str, str] = {}
    for c in candidates:
        if has_hard_anti_fit(c):
            killed[c.id] = ANTI_FIT
            continue
        kept.append(c)
    return kept, killed


def run(ctx: StageContext) -> StageResult:
    signals = [Signal.from_dict(d) for d in artifacts.load_items(ctx.output_dir, "triage")]

    backend = ctx.backends.get("generate")
    if backend is None or ctx.generate_backend_name == "rule":
        candidates = rule.generate(signals)
    else:
        candidates = llm_mod.generate_llm(signals, backend, load_step_config("generate"))

    entered = len(candidates)
    candidates, killed = _screen_anti_fit(candidates)

    path = artifacts.save(
        ctx.output_dir, "generate", [c.to_dict() for c in candidates],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
        extra={"killed": killed},
    )
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "generate",
        survived_ids=[c.id for c in candidates], killed=killed, ts=ctx.today.isoformat(),
    )
    return StageResult("generate", entered=entered, survived=len(candidates), killed=len(killed), artifact=path)
