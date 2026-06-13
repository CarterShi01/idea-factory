"""Stage 5 -- factor scoring + time decay + diversity-aware ranking.

* **alpha** = weighted sum of the factor scores, then multiplied by a time-decay
  term. Opportunity windows decay: the longer ago a signal was observed, the
  more crowded the space tends to be, so older candidates lose ground (but never
  to zero -- they keep a floor).
* **ranking** uses a lightweight MMR (maximal marginal relevance) pass so the
  final list optimizes both *novelty* (each item scores well) and *diversity*
  (the set isn't ten variations of one theme).

Default weights put the most mass on ``pain_intensity`` -- validated need is the
scarce ingredient, per the research.
"""

from __future__ import annotations

import math
import re
from datetime import date

from idea_core.factors import compute_factors
from idea_core.models import IdeaCandidate, ScoredCandidate

DEFAULT_WEIGHTS = {
    "market_freshness": 0.18,
    "pain_intensity": 0.28,
    "build_cost": 0.18,
    "moat_signal": 0.12,
    "competition_density": 0.12,
    "distribution_fit": 0.12,
}

_HALF_LIFE_DAYS = 30.0      # opportunity-window half life
_DECAY_FLOOR = 0.4          # an ancient signal still retains 40% of its alpha
_WORD_RE = re.compile(r"[a-z0-9]+")


def _age_days(observed_on: str, today: date) -> int:
    try:
        observed = date.fromisoformat(observed_on)
    except (ValueError, TypeError):
        return 0
    return max(0, (today - observed).days)


def _decay(observed_on: str, today: date) -> float:
    age = _age_days(observed_on, today)
    raw = math.exp(-math.log(2) / _HALF_LIFE_DAYS * age)
    return _DECAY_FLOOR + (1 - _DECAY_FLOOR) * raw


def score_candidate(
    candidate: IdeaCandidate,
    today: date,
    weights: dict[str, float] | None = None,
) -> ScoredCandidate:
    weights = weights or DEFAULT_WEIGHTS
    factors = compute_factors(candidate)
    base = sum(weights.get(name, 0.0) * value for name, value in factors.items())
    decay = _decay(candidate.observed_on, today)
    return ScoredCandidate(
        candidate=candidate,
        factors=factors,
        alpha=round(base * decay, 4),
        decay=round(decay, 4),
    )


def score(
    candidates: list[IdeaCandidate],
    today: date,
    weights: dict[str, float] | None = None,
) -> list[ScoredCandidate]:
    return [score_candidate(c, today, weights) for c in candidates]


def _tokens(c: IdeaCandidate) -> set[str]:
    return set(_WORD_RE.findall(c.text()))


def _similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def rank(
    scored: list[ScoredCandidate],
    diversity_lambda: float = 0.3,
) -> list[ScoredCandidate]:
    """Re-order via MMR so the head of the list is high-scoring *and* varied.

    ``diversity_lambda`` is how hard we penalize similarity to already-picked
    candidates (0 = pure alpha sort, higher = more diversity pressure).
    """
    pool = sorted(scored, key=lambda s: (-s.alpha, s.candidate.id))
    token_cache = {s.candidate.id: _tokens(s.candidate) for s in pool}
    selected: list[ScoredCandidate] = []

    while pool:
        best, best_mmr = None, None
        for s in pool:
            max_sim = max(
                (_similarity(token_cache[s.candidate.id], token_cache[p.candidate.id]) for p in selected),
                default=0.0,
            )
            mmr = s.alpha - diversity_lambda * max_sim
            # Tie-break on alpha then id for fully deterministic ordering.
            key = (mmr, s.alpha, s.candidate.id)
            if best_mmr is None or key > best_mmr:
                best, best_mmr = s, key
        selected.append(best)
        pool.remove(best)

    return selected
