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
排到前面。

ff2 founder-fit(投资人复评 ff2,本轮迭代③:distribution_fit 权重太低、没起过滤作用):
ff2 里 dist=0.93(获客垄断)和 dist=0.21(纯通用货)**都进了 top**——说明 0.05 的权重让
『获客垄断性』对排序几乎没影响。本轮**大幅提高 distribution_fit 权重**(0.05→0.25,从陪跑
小权重升为与痛点强度并列的排序主力),让『别人复制能不能拿到同样渠道』真正决定排序。**同时加
一道硬降权门**(:data:`_COMMODITY_DIST_GATE`):distribution_fit < 0.3 的『无独占渠道通用货』
alpha 直接乘以重罚系数,确保 dist=0.21 这类即便其他因子高也压不进 top——这就是 ff2 要的
『让获客垄断真正过滤』。保留 7 具名因子契约,权重和为 1.0。
"""

from __future__ import annotations

import math
import re
from datetime import date

from idea_core.factors import compute_factors
from idea_core.models import IdeaCandidate, ScoredCandidate, bucket_of

DEFAULT_WEIGHTS = {
    # ff2: distribution_fit 升为与 pain_intensity 并列的排序主力(0.05→0.25),
    # 让『获客垄断性』真正决定排序;痛点强度/付费信号仍是核心证据轴。
    "pain_intensity": 0.25,       # 痛点强度(真实需求,排序主力之一)
    "distribution_fit": 0.25,     # ff2: 获客垄断性升为排序主力(原 0.05)
    "payment_signal": 0.20,       # 真实付费意愿(最稀缺证据)
    "moat_signal": 0.12,          # 护城河(ff2:略抬,壁垒该影响排序)
    "market_freshness": 0.10,     # 别只靠蹭热点上位
    "build_cost": 0.05,           # 可落地性(round1 称 feasibility)
    "competition_density": 0.03,  # 竞争稀缺度(契约因子,小权重)
}
assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9, "alpha weights must sum to 1.0"

# ff2 硬降权门:获客垄断性是 ff2 唯一真正分水岭。distribution_fit < 阈值 = 无独占渠道的
# 通用货(纯开发者社区/公开市场/谁都能投放),即便痛点/付费/新鲜度都高,也必须压出 top——
# 否则就重蹈 ff2『dist=0.21 仍进 top』的覆辙。这不是软权重能保证的(高的其他因子能把它抬
# 回来),所以用一道乘性硬罚:低于阈值的候选 alpha 乘以 _COMMODITY_DIST_PENALTY。阈值与
# 罚系数对齐 distribution_fit 的分档(referral 起步 0.3,故 <0.3 即『连引荐渠道都没有』)。
_COMMODITY_DIST_THRESHOLD = 0.3
_COMMODITY_DIST_PENALTY = 0.4

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


def _load_funnel() -> dict:
    """漏斗参数(config/funnel.json):切分量 + 分桶权重 + 打散配额。缺失/坏档走内置默认。"""
    import json as _json
    import os as _os
    from pathlib import Path as _Path

    try:
        p = _Path(_os.environ.get("IDEA_FUNNEL_CONFIG", "config/funnel.json"))
        if p.exists():
            return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — bad config never breaks ranking
        pass
    return {}


def _weights_for(source: str, funnel: dict) -> dict[str, float]:
    """按来源取粗排权重集(funnel.coarse.weights_by_source);缺则用 DEFAULT_WEIGHTS。"""
    by_src = (funnel.get("coarse", {}) or {}).get("weights_by_source", {})
    return by_src.get(source) or by_src.get("default") or DEFAULT_WEIGHTS


def score_candidate(
    candidate: IdeaCandidate,
    today: date,
    weights: dict[str, float] | None = None,
) -> ScoredCandidate:
    weights = weights or DEFAULT_WEIGHTS
    factors = compute_factors(candidate)
    base = sum(weights.get(name, 0.0) * value for name, value in factors.items())
    decay = _decay(candidate.observed_on, today)
    # ff2 硬降权门:无独占获客渠道的通用货(distribution_fit 低于阈值)按重罚系数压低,
    # 让『获客垄断』真正过滤 top,而不是被其他高因子抬回来(ff2 dist=0.21 仍进 top 的病根)。
    dist = factors.get("distribution_fit", 1.0)
    commodity_penalty = _COMMODITY_DIST_PENALTY if dist < _COMMODITY_DIST_THRESHOLD else 1.0
    return ScoredCandidate(
        candidate=candidate,
        factors=factors,
        alpha=round(base * decay * commodity_penalty, 4),
        decay=round(decay, 4),
    )


def score(
    candidates: list[IdeaCandidate],
    today: date,
    weights: dict[str, float] | None = None,
) -> list[ScoredCandidate]:
    """粗排打分。``weights`` 给定 → 全量用它(向后兼容);``None`` → **按来源分桶**取权重
    (英文HN主靠热度+需求、中文主靠 founder_fit×痛点,见 config/funnel.json)。"""
    if weights is not None:
        return [score_candidate(c, today, weights) for c in candidates]
    funnel = _load_funnel()
    return [score_candidate(c, today, _weights_for(c.source, funnel)) for c in candidates]


def coarse_select(
    ranked: list[ScoredCandidate],
    k: int,
    en_frac: float = 0.4,
) -> list[ScoredCandidate]:
    """粗排切分:200 → ~k。**分桶保量**——给英文桶留 ``en_frac`` 配额、其余给中文桶,
    各桶内按已排序(alpha/MMR)顺序取,某桶不足则另一桶回填,凑满 k。这样贵的精排(LLM)
    只碰这 k 条,且中英两桶都不会在粗排就被饿死(下游打散配额才有料可分)。"""
    if k <= 0:
        return []
    if len(ranked) <= k:
        return list(ranked)
    en = [s for s in ranked if bucket_of(s.candidate.source) == "en"]
    zh = [s for s in ranked if bucket_of(s.candidate.source) == "zh"]
    en_k = min(len(en), round(k * en_frac))
    zh_k = min(len(zh), k - en_k)
    en_k = min(len(en), k - zh_k)  # 中文不足时英文回填
    picked = en[:en_k] + zh[:zh_k]
    # 保持全局 alpha/MMR 顺序(ranked 已是有序,按其原次序还原)
    keep = {id(s) for s in picked}
    return [s for s in ranked if id(s) in keep]


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
