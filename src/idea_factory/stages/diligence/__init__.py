"""⑥diligence —— 拿证据开庭:便宜前闸 → 对抗批判 → LLM 裁决 → 强制纪律(最贵的一段)。

顺序:规则 kill-gate(.gate,零 token)→ 挂证据(enrich 工件)→ critique(.critique,
devil's advocate)→ judge(.judge,LLM-as-judge)→ 引证校验/证据接地/强制分布
(.enforce,纯代码)→ persona 压力测试(.persona_pressure,advisory,不改判决)。
critique/judge/persona 由 backends 旗门控,默认 None = 零 token(成本梯度)。
读:ideas.json + evidence.json  写:verdicts.json + ledger(verdicts/impressions/traces)
只 import contract / runtime / factors。可能抛 PendingHandoff,由 CLI 接。
"""

from __future__ import annotations

from idea_factory.contract import artifacts
from idea_factory.contract.models import KILL, Evaluation
from idea_factory.contract.stage import StageContext, StageResult
from idea_factory.runtime import ledger
from idea_factory.runtime.llm import load_step_config

from . import apply, critique as critique_mod
from . import enforce, gate
from . import judge as judge_mod
from . import persona_pressure as pp_mod


def run(ctx: StageContext) -> StageResult:
    ideas = artifacts.load_items(ctx.output_dir, "rank")
    ideas_by_id = {i.get("id", ""): i for i in ideas}

    floor = ctx.floor if ctx.floor is not None else gate.DEFAULT_FLOOR
    evaluations = gate.evaluate_all(ideas, floor=floor)

    # 证据先于评审:evidence_block 要喂进 critique/judge 的 prompt。
    env = artifacts.load(ctx.output_dir, "enrich")
    evidence_by_id: dict[str, list] = {}
    for ev in env["items"]:
        evidence_by_id.setdefault(ev.get("candidate_id", ""), []).append(ev)
    gate_by_id = {
        cid: (bool(g.get("ready")), list(g.get("missing", [])))
        for cid, g in (env.get("gate", {}) or {}).items()
    }
    apply.apply_evidence(evaluations, evidence_by_id, gate_by_id)

    if ctx.backends.get("critique") is not None and ctx.critique:
        critique_mod.critique_survivors(
            evaluations, ideas_by_id, ctx.backends["critique"], load_step_config("critique"),
            trace_data_dir=ctx.data_dir, trace_run_id=ctx.run_id,
        )
    if ctx.backends.get("judge") is not None:
        evaluations = judge_mod.judge_survivors(
            evaluations, ideas_by_id, ctx.backends["judge"], load_step_config("judge"),
            trace_data_dir=ctx.data_dir, trace_run_id=ctx.run_id,
        )

    evaluations = enforce.enforce_citation(evaluations)
    evaluations = enforce.enforce_evidence_grounding(evaluations)
    max_frac = ctx.max_pursue_frac if ctx.max_pursue_frac is not None else enforce.DEFAULT_MAX_PURSUE_FRAC
    evaluations = enforce.enforce_forced_distribution(evaluations, max_pursue_frac=max_frac)

    # persona 压力测试:只碰最终 PURSUE 幸存者(量最小),advisory,不改判决。
    if ctx.backends.get("persona_pressure") is not None:
        evaluations = pp_mod.run_persona_pressure(
            evaluations, ideas_by_id, ctx.backends["persona_pressure"],
            load_step_config("persona_pressure"),
        )

    path = artifacts.save(
        ctx.output_dir, "diligence", [e.to_dict() for e in evaluations],
        run_id=ctx.run_id, week=ctx.week, today=ctx.today,
    )
    survived = [e.idea_id for e in evaluations if e.verdict != KILL]
    killed_map = {
        e.idea_id: (e.killed_by[0] if e.killed_by else "eval_kill")
        for e in evaluations if e.verdict == KILL
    }
    ledger.log_impressions_bulk(
        ctx.data_dir, ctx.run_id, ctx.week, "diligence",
        survived_ids=survived, killed=killed_map, ts=ctx.today.isoformat(),
    )
    for e in evaluations:
        ledger.log_verdict(ctx.data_dir, e.to_dict(), actor="system", ts=ctx.today.isoformat())

    return StageResult(
        "diligence", entered=len(ideas), survived=len(survived), killed=len(killed_map),
        artifact=path,
    )
