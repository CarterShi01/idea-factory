"""Idea Factory -- one package, eight first-class pipeline stages.

Layering (enforced by tests/test_stage_isolation.py)::

    contract <- runtime <- factors <- stages <- pipeline <- cli

* ``contract``  data model + stage-boundary artifacts (改字段=创始人点头)
* ``runtime``   cross-cutting infra: llm / ledger / versioning / config / textsim
* ``factors``   pure candidate->float factor library (单一真相源)
* ``stages``    the eight stages; siblings NEVER import each other
* ``pipeline``  the only composer; runs any contiguous stage range
* ``cli``       single `idea` entry point
"""

from idea_factory.contract.models import (  # noqa: F401 -- public API
    CONFIDENCE_REAL,
    CONFIDENCE_SYNTHETIC,
    Evaluation,
    Evidence,
    IdeaCandidate,
    KILL,
    Outcome,
    PURSUE,
    REVIEW,
    ScoredCandidate,
    Signal,
    SOURCE_BRAIN,
    SOURCE_EXTERNAL,
    SOURCE_PERSONA,
    bucket_of,
    sort_evaluations,
)
