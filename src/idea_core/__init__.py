"""idea_core -- the shared contract for the Idea Factory system.

Holds the data model (:mod:`idea_core.models`) and the factor library
(:mod:`idea_core.factors`). Both halves of the system import from here:

* ``idea_gen``  -- generation + scoring
* ``idea_eval``  -- evaluation + kill-gate

Keeping the model and the factor definitions in one place is deliberate: it is
the single source of truth, so the generation and evaluation sides can never
drift apart (the freqtrade lesson from docs/research/03).
``idea_gen`` and ``idea_eval`` depend on ``idea_core`` but never on each other.
"""

from .factors import FACTORS, compute_factors
from .models import (
    CONFIDENCE_REAL,
    CONFIDENCE_SYNTHETIC,
    SOURCE_BRAIN,
    SOURCE_EXTERNAL,
    SOURCE_PERSONA,
    IdeaCandidate,
    ScoredCandidate,
    Signal,
)

__all__ = [
    "FACTORS",
    "compute_factors",
    "Signal",
    "IdeaCandidate",
    "ScoredCandidate",
    "SOURCE_EXTERNAL",
    "SOURCE_BRAIN",
    "SOURCE_PERSONA",
    "CONFIDENCE_REAL",
    "CONFIDENCE_SYNTHETIC",
]
