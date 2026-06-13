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

from . import collect, dedup, export, generate, normalize, ranks


def _llm_backend(name: str, step: str, today: date, job_dir: str | Path) -> LLMBackend:
    """Build an LLM backend; CC-handoff gets a dated job name for its file pack."""
    if name == "cc":
        return get_backend("cc", job_dir=job_dir, job_name=f"{step}-{today.isoformat()}")
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
) -> PipelineResult:
    """Run the generation pipeline.

    ``gen_backend``: ``"rule"`` (offline default, zero token) or an LLM backend
    name (``"router"`` Tencent / ``"cc"`` manual handoff / ``"mock"``). When it is
    an LLM backend, generation goes through ``config/llm/generate.json``.
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    today = today or date.today()

    # 1. collect (offline) -> 2. normalize -> 3. dedup
    raw = collect.collect_all(data_dir, sources=sources)
    signals = normalize.normalize(raw)
    kept, _dropped = dedup.dedupe_signals(signals, seen_keys=seen_keys)

    # 4. generate (over-generate) -> 5. score -> rank
    if gen_backend == "rule":
        candidates = generate.generate(kept)
    else:
        backend = llm or _llm_backend(gen_backend, "generate", today, job_dir)
        candidates = generate.generate_llm(kept, backend, load_step_config("generate"))
    scored = ranks.score(candidates, today=today, weights=weights)
    ranked = ranks.rank(scored)

    # 7. export
    json_path = output_dir / "ideas.json"
    md_path = output_dir / "ideas.md"
    export.write_json(ranked, json_path)
    export.write_markdown(ranked, md_path, today=today, top_n=top_n)

    return PipelineResult(
        raw_count=len(raw),
        signal_count=len(signals),
        deduped_count=len(kept),
        candidate_count=len(candidates),
        scored=ranked,
        json_path=json_path,
        markdown_path=md_path,
    )
