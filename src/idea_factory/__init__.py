"""Idea Factory -- offline MVP that turns three-source signals into ranked
startup-idea candidates.

Pipeline: collect -> normalize -> dedup -> generate -> score -> rank -> export.
See ``docs/research/`` for the design rationale and roadmap.
"""

from .pipeline import PipelineResult, run_pipeline

__version__ = "0.1.0"
__all__ = ["run_pipeline", "PipelineResult", "__version__"]
