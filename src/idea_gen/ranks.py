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

Round 2(投资人复评严重度④:alpha 排序过度依赖 market_freshness、付费信号没进排序)。
按 round1 给的方向重配权:把**痛点强度**和新增的**付费信号**(真实付费意愿是最稀缺、最值钱
的证据)抬成排序主力,把**市场新鲜度**降下来——避免『蹭热点但没人愿付费』的 idea 仅凭新鲜度
排到前面。round1 建议 pain 0.35 / payment 0.25 / freshness 0.15 / feasibility 0.15 /
moat 0.10;此处在保留 6 具名因子契约的前提下纳入全部七因子(竞争稀缺度/触达匹配度给小权重),
权重和为 1.0。
"""

from __future__ import annotations

import math
import re
from datetime import date

from idea_core.factors import compute_factors
from idea_core.models import IdeaCandidate, ScoredCandidate

DEFAULT_WEIGHTS = {
    "pain_intensity": 0.35,       # round1: 痛点强度是排序第一主力
    "payment_signal": 0.25,       # round1 新增:真实付费意愿是最稀缺证据
    "market_freshness": 0.15,     # round1: 从过重降到 0.15(别只靠蹭热点上位)
    "build_cost": 0.10,           # 可落地性(round1 称 feasibility)
    "moat_signal": 0.07,          # round1: 护城河 ~0.10 档
    "distribution_fit": 0.05,     # 触达匹配度(契约因子,小权重)
    "competition_density": 0.03,  # 竞争稀缺度(契约因子,小权重)
}
assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9, "alpha weights must sum to 1.0"

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


def select_diverse_top_n(
    ranked: list[ScoredCandidate],
    n: int,
    threshold: float = 0.6,
) -> list[ScoredCandidate]:
    """Pick the final Top-N so near-duplicates don't crowd the head.

    Round 3(投资人复评 #3:"15 条里 4 条都是『语音备忘转任务』"):MMR's soft
    similarity penalty still let several near-identical ideas occupy the head when
    they all scored well. This is a *hard* lexical de-cluster on top of the MMR
    order: walk the already-ranked list and skip a candidate if its token-set
    Jaccard against any already-picked item is ≥ ``threshold``. Skipped items are
    parked and used to backfill only if we'd otherwise return fewer than ``n``
    (so the list length is preserved when the pool is thin).

    Operates on the *output* order of :func:`rank`, so the head stays high-alpha
    and now also non-redundant. Optimizes Non-Duplicate Ratio of the digest.
    Stdlib lexical Jaccard only — semantic/embedding de-dup is roadmap stage 3.
    """
    if n <= 0:
        return []
    token_cache = {s.candidate.id: _tokens(s.candidate) for s in ranked}
    picked: list[ScoredCandidate] = []
    parked: list[ScoredCandidate] = []

    for s in ranked:
        if len(picked) >= n:
            break
        toks = token_cache[s.candidate.id]
        if any(_similarity(toks, token_cache[p.candidate.id]) >= threshold for p in picked):
            parked.append(s)
            continue
        picked.append(s)

    # Backfill from parked only to reach n if the diverse pool ran dry — never
    # drop below the requested count when candidates exist.
    if len(picked) < n:
        picked.extend(parked[: n - len(picked)])

    return picked
