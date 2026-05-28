"""Keyword matching between freshly collected signals and existing ideas.

When new external signals arrive (see :mod:`idea_factory.collect`), this module
finds the existing idea candidates they most plausibly relate to via simple
keyword overlap, so the user can be nudged: "this may be related to one of your
ideas". Intentionally lightweight and offline — no model calls.
"""

from __future__ import annotations

import re
from typing import Any

# Short, low-signal tokens to ignore when comparing items to ideas.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "from", "your", "you",
        "are", "but", "not", "all", "any", "can", "has", "have", "into",
        "out", "via", "about", "more", "less", "new", "app", "tool", "ai",
        "inspired", "approach", "further", "takes", "taking", "take",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _join(values: Any) -> str:
    if isinstance(values, list):
        return " ".join(str(v) for v in values)
    return str(values or "")


def item_keywords(item: dict[str, Any]) -> set[str]:
    """Keyword set derived from a collected item's text fields."""
    parts = [
        str(item.get("name", "")),
        str(item.get("tagline", "")),
        str(item.get("description", "")),
        _join(item.get("categories")),
    ]
    return _tokenize(" ".join(parts))


def idea_keywords(idea: dict[str, Any]) -> set[str]:
    """Keyword set derived from an idea candidate's text fields."""
    parts = [
        str(idea.get("pitch", "")),
        str(idea.get("category", "")),
        str(idea.get("target_audience", "")),
        str(idea.get("pain_point", "")),
        str(idea.get("source_product_name", "")),
    ]
    return _tokenize(" ".join(parts))


def find_related_ideas(
    items: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    *,
    min_overlap: int = 1,
) -> list[dict[str, Any]]:
    """Return item↔idea matches sharing at least ``min_overlap`` keywords.

    Each match is a dict with ``item_id``, ``item_name``, ``item_source``,
    ``idea_id``, ``idea_pitch``, ``shared_keywords`` (sorted) and ``score``
    (overlap count). Results are sorted by ``score`` descending, then by
    ``item_id`` / ``idea_id`` for stable ordering.
    """
    idea_kw = [(idea, idea_keywords(idea)) for idea in ideas]
    matches: list[dict[str, Any]] = []
    for item in items:
        keywords = item_keywords(item)
        if not keywords:
            continue
        for idea, other in idea_kw:
            shared = keywords & other
            if len(shared) >= min_overlap:
                matches.append(
                    {
                        "item_id": item.get("id", ""),
                        "item_name": item.get("name", ""),
                        "item_source": item.get("source", ""),
                        "idea_id": idea.get("id", ""),
                        "idea_pitch": idea.get("pitch", ""),
                        "shared_keywords": sorted(shared),
                        "score": len(shared),
                    }
                )
    matches.sort(key=lambda m: (-m["score"], str(m["item_id"]), str(m["idea_id"])))
    return matches


def format_suggestion(match: dict[str, Any]) -> str:
    """Render a single match as a user-facing suggestion line."""
    shared = "、".join(match.get("shared_keywords", []))
    return (
        f'这条可能和你某个 idea 相关：'
        f'新信号「{match.get("item_name", "")}」'
        f'(来源 {match.get("item_source", "")}) '
        f'↔ idea {match.get("idea_id", "")}「{match.get("idea_pitch", "")}」'
        f'(共同关键词: {shared})'
    )
