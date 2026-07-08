"""层4 唯一编排者:按段顺序跑任意连续区间,段间只经磁盘工件。

八段中可跑的漏斗段是 recall→triage→generate→rank→enrich→diligence→portfolio
(retro 是 CLI 侧回流,不在漏斗里)。每段 = ``stages/<name>/run(ctx)``,读上一段
的工件、写自己的工件 —— 所以 ``run(from_stage="diligence")`` 天然就是单段重跑/
断点续跑:输入从盘上来。

成本梯度落点:rank→enrich 之间的 ideas.json 仍是便宜/昂贵半场的缝;LLM 段
(generate/critique/judge/persona_pressure)由 backend 旗门控,默认零 token。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idea_factory.contract import artifacts
from idea_factory.contract.stage import STAGES, StageContext, StageResult
from idea_factory.runtime import ledger
from idea_factory.runtime.llm import LLMBackend, backend_for_step

from idea_factory.stages import diligence, enrich, generate, portfolio, rank, recall, triage

_RUNNERS = {
    "recall": recall.run,
    "triage": triage.run,
    "generate": generate.run,
    "rank": rank.run,
    "enrich": enrich.run,
    "diligence": diligence.run,
    "portfolio": portfolio.run,
}


@dataclass
class RunResult:
    run_id: str = ""
    week: str = ""
    stages: list[StageResult] = field(default_factory=list)

    def stage(self, name: str) -> StageResult | None:
        return next((s for s in self.stages if s.stage == name), None)


def _stage_range(from_stage: str | None, to_stage: str | None, only: str | None) -> list[str]:
    if only:
        return [only]
    lo = STAGES.index(from_stage) if from_stage else 0
    hi = STAGES.index(to_stage) if to_stage else len(STAGES) - 1
    if lo > hi:
        raise ValueError(f"--from {from_stage} comes after --to {to_stage}")
    return list(STAGES[lo:hi + 1])


def _build_backends(
    names: dict[str, str],
    today: date,
    job_dir: str | Path,
    injected: dict[str, LLMBackend | None] | None = None,
) -> dict[str, LLMBackend | None]:
    """step -> backend(or None=off)。``injected`` 里的预построй后端优先(测试缝)。"""
    injected = injected or {}
    out: dict[str, LLMBackend | None] = {}
    off = {"none", "rule", "static", "", None}
    for step, name in names.items():
        if step in injected and injected[step] is not None:
            out[step] = injected[step]
        elif name in off:
            out[step] = None
        else:
            out[step] = backend_for_step(name, step, today.isoformat(), job_dir)
    return out


def run(
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/processed",
    today: date | None = None,
    from_stage: str | None = None,
    to_stage: str | None = None,
    only: str | None = None,
    sources: list[str] | None = None,
    top_n: int = 15,
    weekly_top_n: int = 3,
    floor: float | None = None,
    max_pursue_frac: float | None = None,
    live: bool = False,
    use_state: bool = False,
    critique: bool = True,
    version: bool = True,
    generate_backend: str = "rule",
    judge_backend: str = "none",
    persona_backend: str = "static",
    persona_pressure_backend: str = "none",
    job_dir: str | Path = "data/llm_jobs",
    backends: dict[str, LLMBackend | None] | None = None,
) -> RunResult:
    """Run a contiguous stage range (default: the whole funnel).

    ``backends``(测试缝):step -> 预构建后端,优先于按名构建。judge_backend 同时
    供 critique 用(与旧行为一致:critique 是 judge 的前置对抗步)。
    May raise ``PendingHandoff`` (CC-handoff) -- the CLI reports and pauses.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    today = today or date.today()
    stages_to_run = _stage_range(from_stage, to_stage, only)

    # run_id:从头跑就铸新的;续跑(--from/--only)从输入工件继承同一条 run 线。
    if stages_to_run[0] == "recall":
        run_id = ledger.next_run_id(data_dir, today.isoformat(), kind="run")
        week = ledger.week_of(today.isoformat())
    else:
        prev = STAGES[STAGES.index(stages_to_run[0]) - 1]
        env = artifacts.load(output_dir, prev)
        run_id = env.get("run_id", "") or ledger.next_run_id(data_dir, today.isoformat(), kind="run")
        week = env.get("week", "") or ledger.week_of(today.isoformat())

    built = _build_backends(
        {
            "generate": generate_backend,
            "critique": judge_backend if critique else "none",
            "judge": judge_backend,
            "persona_sim": persona_backend,
            "persona_pressure": persona_pressure_backend,
        },
        today, job_dir, injected=backends,
    )

    # Cross-stage glue (composer-only, same reason ctx.backends is pre-built
    # here rather than by the stage itself): portfolio's weekly_report wants a
    # read-only calibrate summary, but portfolio may not import its sibling
    # retro stage (isolation rule) -- so pipeline.py computes it and hands the
    # plain-dict result down via StageContext. Skipped when portfolio isn't in
    # this run's stage range (nothing would consume it).
    calibrate_report = None
    if "portfolio" in stages_to_run:
        from idea_factory.stages.retro import calibrate

        calibrate_report = calibrate.suggest_weights(data_dir)

    ctx = StageContext(
        data_dir=data_dir, output_dir=output_dir, today=today,
        run_id=run_id, week=week, backends=built,
        sources=sources, top_n=top_n, weekly_top_n=weekly_top_n,
        floor=floor, max_pursue_frac=max_pursue_frac,
        live=live, use_state=use_state, critique=critique, version=version,
        generate_backend_name=generate_backend,
        calibrate_report=calibrate_report,
    )

    result = RunResult(run_id=run_id, week=week)
    for name in stages_to_run:
        result.stages.append(_RUNNERS[name](ctx))

    # 动态模式的跨段回喂(组合器胶水,不属于任何单段):候选的 target_user 派生新人群,
    # 持久化供下轮 recall "全选"纳入。
    if use_state and "generate" in stages_to_run:
        from idea_factory.stages.recall.persona import load_taxonomy
        from idea_factory.stages.recall.persona.derive import update_derived
        from idea_factory.contract.models import IdeaCandidate

        cands = [IdeaCandidate.from_dict(d) for d in artifacts.load_items(output_dir, "generate")]
        update_derived(cands, load_taxonomy(), data_dir / "state" / "derived_segments.json")

    return result
