"""Stage 3 -- drop signals we have effectively already seen.

Two levels, mirroring the "point-in-time / anti-crowding" idea from the quant
research: feeding the same opportunity in repeatedly should not produce
repeated output.

* **Exact**: identical ``dedup_key`` (lexical fingerprint from normalize).
* **Lexical near-duplicate**: token-set Jaccard similarity above a threshold.

A persistent "seen" store (across daily runs) is roadmap stage 3; this MVP
keeps it optional via ``seen_keys`` so the default demo stays reproducible.
"""

from __future__ import annotations

import re

from idea_core.models import Signal

# 英文按词、中文(CJK)按单字切分 —— 中文近重判断才有意义。
_WORD_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def _token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def dedupe_signals(
    signals: list[Signal],
    threshold: float = 0.8,
    seen_keys: set[str] | None = None,
) -> tuple[list[Signal], list[Signal]]:
    """Return ``(kept, dropped)``.

    ``seen_keys`` (optional) carries fingerprints from previous runs; matching
    signals are dropped as already-seen. The set is mutated in place with the
    keys of kept signals so callers can persist it.
    """
    seen_keys = seen_keys if seen_keys is not None else set()
    kept: list[Signal] = []
    dropped: list[Signal] = []
    kept_tokens: list[set[str]] = []

    for sig in signals:
        if sig.dedup_key in seen_keys:
            dropped.append(sig)
            continue
        tokens = _token_set(sig.pain_statement or sig.title)
        if any(jaccard(tokens, prev) >= threshold for prev in kept_tokens):
            dropped.append(sig)
            continue
        kept.append(sig)
        kept_tokens.append(tokens)
        seen_keys.add(sig.dedup_key)

    return kept, dropped
