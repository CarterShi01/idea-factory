"""Lexical text-similarity primitives shared across stages.

Hoisted verbatim from the old ``idea_gen.dedup`` -- English tokenized by word,
CJK by single character, so near-duplicate detection works for Chinese text too.

⚠️ This is deliberately NOT the only tokenizer in the codebase. The rank stage's
MMR (``[a-z0-9]+``, no lowercasing of CJK) and the portfolio stage's de-cluster
(``[\\w一-鿿]+`` runs) each keep their own private tokenizer -- unifying them
would silently change ranking/diversify order. Only true duplicates of the
dedup tokenizer (triage dedup, generate fusion, persona crosscheck) import this.
"""

from __future__ import annotations

import re

# 英文按词、中文(CJK)按单字切分 —— 中文近重判断才有意义。
_WORD_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
