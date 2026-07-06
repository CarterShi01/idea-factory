"""④rank 的选择半边:MMR 重排 + 粗排切分 + 硬去聚类(纯代码,零 token)。

⚠️ 本文件的分词器(``[a-z0-9]+``,不含 CJK、不小写 CJK)与 runtime.textsim 的
dedup 分词器**故意不同**——统一会静默改变 MMR/打散顺序(见 textsim 模块注)。
"""

from __future__ import annotations

import re

from idea_factory.contract.models import IdeaCandidate, ScoredCandidate, bucket_of

_WORD_RE = re.compile(r"[a-z0-9]+")

def _tokens(c: IdeaCandidate) -> set[str]:
    return set(_WORD_RE.findall(c.text()))


def _similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


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
