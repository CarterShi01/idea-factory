"""idea_eval pipeline -- read idea_gen's candidates, screen them, write results.

    ideas.json (from idea_gen)  ->  evaluate (kill-gate + rubric)  ->  screened.json + decision_memos.md

idea_eval depends only on its own modules and ``idea_core``; it never imports
``idea_gen``. The two halves talk through the ``ideas.json`` file on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from idea_core.llm import LLMBackend, get_backend, load_step_config

from . import evaluate, export
from .evaluate import KILL, PURSUE, REVIEW


def _llm_backend(name: str, today: date, job_dir: str | Path) -> LLMBackend:
    """Build an LLM backend; CC-handoff gets a dated job name for its file pack."""
    if name == "cc":
        return get_backend("cc", job_dir=job_dir, job_name=f"judge-{today.isoformat()}")
    return get_backend(name)


@dataclass
class EvalResult:
    evaluated: int = 0
    pursue: int = 0
    review: int = 0
    killed: int = 0
    evaluations: list = field(default_factory=list)
    json_path: Path | None = None
    memos_path: Path | None = None


def run_evaluation(
    input_path: str | Path = "data/processed/ideas.json",
    output_dir: str | Path = "data/processed",
    today: date | None = None,
    floor: float = evaluate.DEFAULT_FLOOR,
    top_n: int = 20,
    judge_backend: str = "none",
    llm: LLMBackend | None = None,
    job_dir: str | Path = "data/llm_jobs",
) -> EvalResult:
    """Screen idea_gen's candidates.

    ``judge_backend``: ``"none"`` (rule-only, offline default, zero token) or an
    LLM backend name (``"router"`` / ``"cc"`` / ``"mock"``). When set, the rule
    kill-gate runs first and the LLM judge (B) only sees the survivors (Top-K),
    using ``config/llm/judge.json``.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    today = today or date.today()

    ideas = json.loads(input_path.read_text(encoding="utf-8"))
    evaluations = evaluate.evaluate_all(ideas, floor=floor)

    if judge_backend != "none":
        backend = llm or _llm_backend(judge_backend, today, job_dir)
        ideas_by_id = {i.get("id", ""): i for i in ideas}
        evaluations = evaluate.judge_survivors(
            evaluations, ideas_by_id, backend, load_step_config("judge")
        )

    json_path = output_dir / "screened.json"
    memos_path = output_dir / "decision_memos.md"
    export.write_json(evaluations, json_path)
    export.write_memos(evaluations, memos_path, today=today, top_n=top_n)

    return EvalResult(
        evaluated=len(evaluations),
        pursue=sum(1 for e in evaluations if e.verdict == PURSUE),
        review=sum(1 for e in evaluations if e.verdict == REVIEW),
        killed=sum(1 for e in evaluations if e.verdict == KILL),
        evaluations=evaluations,
        json_path=json_path,
        memos_path=memos_path,
    )
