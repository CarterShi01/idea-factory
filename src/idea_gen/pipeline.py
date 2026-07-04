"""Pipeline orchestration -- compose the stages end to end.

    collect -> normalize -> dedup -> generate -> dedup(candidates implicit)
            -> score -> rank -> export

This is the only module that knows the full stage order. Each stage stays a
small, independently testable function in its own module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idea_core.llm import LLMBackend, get_backend, load_step_config
from idea_core.state import SeenStore, SignalHistory
from idea_core.trends import classify

from . import collect, dedup, export, generate, normalize, ranks


def _dynamic_dedup_and_trends(signals, state_dir: Path, today: date):
    """动态模式:SeenStore 跨日去重 + SignalHistory 趋势,把 trend_status/growth_speed 回填到信号。"""
    today_iso = today.isoformat()
    seen = SeenStore.load(state_dir / "seen.jsonl")
    hist = SignalHistory.load(state_dir / "signal_history.jsonl")

    # 历史记录所有信号的话题(含已见过的,以追踪持续升温);只保留"新"信号
    for s in signals:
        hist.add(s.topic, s.observed_on or today_iso)
    fresh = [s for s in signals if seen.observe(s.dedup_key, today_iso)]
    # 批内再做一次词法近重去重
    fresh, _dropped = dedup.dedupe_signals(fresh)
    # 趋势分类 → 回填
    for s in fresh:
        status, speed = classify(hist.series(s.topic, window=30, end=today_iso))
        s.trend_status, s.growth_speed = status, speed

    seen.save()
    hist.save()
    return fresh


def _llm_backend(name: str, step: str, today: date, job_dir: str | Path) -> LLMBackend:
    """Build an LLM backend; CC-handoff gets a dated job name for its file pack."""
    if name == "cc":
        return get_backend("cc", job_dir=job_dir, job_name=f"{step}-{today.isoformat()}")
    if name == "dify":
        return get_backend("dify", step=step)  # per-step Dify app/key; prompt lives in the flow
    return get_backend(name)


@dataclass
class PipelineResult:
    """Summary of one pipeline run (returned to the CLI for reporting)."""

    raw_count: int = 0
    signal_count: int = 0
    deduped_count: int = 0
    candidate_count: int = 0
    scored: list = field(default_factory=list)
    json_path: Path | None = None
    markdown_path: Path | None = None


def run_pipeline(
    data_dir: str | Path = "data",
    output_dir: str | Path = "data/processed",
    today: date | None = None,
    top_n: int = 15,
    sources: list[str] | None = None,
    weights: dict[str, float] | None = None,
    seen_keys: set[str] | None = None,
    gen_backend: str = "rule",
    llm: LLMBackend | None = None,
    job_dir: str | Path = "data/llm_jobs",
    live: bool = False,
    use_state: bool = False,
    persona_backend: str = "static",
) -> PipelineResult:
    """Run the generation pipeline.

    ``gen_backend``: ``"rule"`` (offline default, zero token) or an LLM backend
    name (``"router"`` Tencent / ``"cc"`` manual handoff / ``"mock"``).
    ``live``: 允许联网型适配器抓取（默认离线）。
    ``use_state``: 启用持久状态（SeenStore 跨日去重 + SignalHistory 趋势）—— 这是"动态"
    模式;默认 False 保持 demo 幂等(同输入两次结果相同)。
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    today = today or date.today()

    # 1. collect -> 2. normalize -> 3. dedup (+ 动态状态/趋势)
    persona_llm = None if persona_backend == "static" else _llm_backend(persona_backend, "persona_sim", today, job_dir)
    raw = collect.collect_all(data_dir, sources=sources, live=live, persona_llm=persona_llm)
    signals = normalize.normalize(raw)
    if use_state:
        kept = _dynamic_dedup_and_trends(signals, data_dir / "state", today)
    else:
        kept, _dropped = dedup.dedupe_signals(signals, seen_keys=seen_keys)

    # 4. generate (over-generate) -> 5. score -> rank
    if gen_backend == "rule":
        candidates = generate.generate(kept)
    else:
        backend = llm or _llm_backend(gen_backend, "generate", today, job_dir)
        candidates = generate.generate_llm(kept, backend, load_step_config("generate"))

    # 动态模式:从候选的 target_user 自动派生新人群,持久化供下轮"全选"纳入
    if use_state:
        from .persona import load_taxonomy
        from .persona.derive import update_derived

        update_derived(candidates, load_taxonomy(), data_dir / "state" / "derived_segments.json")

    # 5. 粗排(召回→粗排):按来源分桶因子打分 + MMR 排序 + 切到 coarse_k。
    # 漏斗(docs/design/idea-funnel.md):idea_gen 负责召回+粗排,ideas.json 从"全量转储"
    # 升级为"粗排后的候选池"——贵的 LLM 精排(idea_eval)只碰这一池,不再跑全量。
    funnel = ranks._load_funnel()
    coarse_k = int((funnel.get("cut_sizes", {}) or {}).get("coarse_k", 50))
    scored = ranks.score(candidates, today=today, weights=weights)
    ranked = ranks.rank(scored)
    coarse = ranks.coarse_select(ranked, coarse_k)
    # 人看的摘要在粗排池上再做一次硬去聚类(防近重刷屏)。
    digest = ranks.select_diverse_top_n(coarse, n=top_n)

    # 7. export —— ideas.json = 粗排池(给 idea_eval 精排),ideas.md = 摘要
    json_path = output_dir / "ideas.json"
    md_path = output_dir / "ideas.md"
    export.write_json(coarse, json_path)
    export.write_markdown(digest, md_path, today=today, top_n=top_n)

    return PipelineResult(
        raw_count=len(raw),
        signal_count=len(signals),
        deduped_count=len(kept),
        candidate_count=len(candidates),
        scored=coarse,
        json_path=json_path,
        markdown_path=md_path,
    )
