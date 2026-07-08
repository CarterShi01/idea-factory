"""Stage interface: the uniform contract every pipeline stage implements.

Each stage package (``idea_factory.stages.<name>``) exposes exactly one entry
point::

    def run(ctx: StageContext) -> StageResult

A stage reads its input artifact(s) from disk (see :mod:`.artifacts`), does its
work, writes its output artifact, and logs its impressions to the ledger. The
pipeline is then nothing but a sequence of ``run(ctx)`` calls -- which is what
makes single-stage rerun / resume (``idea run --only diligence``) free.

Layering: this module is pure data (dataclasses + constants). LLM backends are
*built by the pipeline* (which may import runtime) and handed in via
``StageContext.backends``; stages never construct backends themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# Canonical stage order (the runnable funnel; retro is CLI-side, not a funnel stage).
STAGES = ("recall", "triage", "generate", "rank", "enrich", "diligence", "portfolio")


@dataclass
class StageContext:
    """Everything a stage is allowed to know about the run."""

    data_dir: Path = Path("data")
    output_dir: Path = Path("data/processed")
    today: date = None  # type: ignore[assignment]  # pipeline always sets it
    run_id: str = ""
    week: str = ""
    # LLM backends keyed by step name (generate / critique / judge /
    # persona_pressure / persona_sim). Missing key or None = that LLM step is
    # off (cost-gradient default: zero tokens). Pre-built by the pipeline.
    backends: dict = field(default_factory=dict)
    # knobs (flat on purpose -- stages read what they need, ignore the rest)
    sources: list[str] | None = None
    top_n: int = 15
    weekly_top_n: int = 3
    floor: float | None = None            # diligence gate floor (None -> stage default)
    max_pursue_frac: float | None = None  # diligence forced-distribution cap
    live: bool = False                    # allow network in recall/enrich fetchers
    use_state: bool = False               # cross-day SeenStore + trend series
    critique: bool = True                 # devil's-advocate pass before the judge
    version: bool = True                  # snapshot processed/ after portfolio
    generate_backend_name: str = "rule"   # "rule" = offline template path
    # Pre-computed by pipeline.py (composer-only cross-stage glue, same reason
    # backends are pre-built): retro.calibrate's read-only factor-correlation
    # report, handed to portfolio's weekly_report tail. None = not computed
    # (e.g. portfolio isn't in this run's stage range) or calibrate never ran.
    calibrate_report: dict | None = None


@dataclass
class StageResult:
    stage: str
    entered: int = 0
    survived: int = 0
    killed: int = 0
    artifact: Path | None = None
    extra: dict = field(default_factory=dict)  # stage-specific summary (paths, counts)
