"""idea_gen -- the generation + scoring half of the Idea Factory system.

Turns three-source signals into ranked startup-idea candidates and hands them
off (as ``data/processed/ideas.json``) to ``idea_eval`` for screening.

Pipeline: collect -> normalize -> dedup -> generate -> score -> rank -> export.
Shares its data model and factor library with ``idea_eval`` via ``idea_core``.
See ``docs/research/`` for the design rationale and roadmap.
"""

from .pipeline import PipelineResult, run_pipeline

__version__ = "0.1.0"
__all__ = ["run_pipeline", "PipelineResult", "__version__"]
