"""Generate mock startup idea candidates from normalized product records.

This is intentionally rule-based and offline. Each product can spawn one or
more idea candidates derived from its categories, target users, and pain
points. No external API calls.
"""

from __future__ import annotations

import hashlib
from typing import Any

TEMPLATES = [
    "An AI copilot for {audience} that eliminates {pain}, inspired by {name}.",
    "A vertical {category} tool focused on {audience}, taking {name}'s approach further.",
    "A community-driven take on {name} that crowdsources solutions to {pain}.",
]

RANK_MIN = 1
RANK_MAX = 5

# Inspiration source (灵感来源) used when a product carries no explicit source,
# i.e. the hand-authored offline sample fixtures.
DEFAULT_INSPIRATION_SOURCE = "sample"


def _first_or(values: list[str], default: str) -> str:
    return values[0] if values else default


def _rank_for_index(index: int) -> int:
    """Deterministically assign a mock rank in [RANK_MIN, RANK_MAX] for an idea index."""
    span = RANK_MAX - RANK_MIN + 1
    return RANK_MAX - (index % span)


def _idea_id(source_product_id: str, pitch_index: int) -> str:
    """Deterministic 8-char hex id for an idea identified by its source product and pitch index."""
    digest = hashlib.sha256(f"{source_product_id}:{pitch_index}".encode()).hexdigest()
    return digest[:8]


def generate_ideas_for_product(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Produce idea candidates for a single normalized product."""
    name = product.get("name") or "an unnamed product"
    audience = _first_or(product.get("target_users", []), "early adopters")
    category = _first_or(product.get("categories", []), "general")
    pains = product.get("pain_points") or ["an unmet user need"]

    source_product_id = product.get("id", "")
    inspiration_source = product.get("source") or DEFAULT_INSPIRATION_SOURCE
    ideas: list[dict[str, Any]] = []
    for i, template in enumerate(TEMPLATES):
        pain = pains[i % len(pains)]
        pitch = template.format(
            name=name,
            audience=audience,
            category=category,
            pain=pain,
        )
        ideas.append(
            {
                "id": _idea_id(source_product_id, i),
                "source_product_id": source_product_id,
                "source_product_name": name,
                "inspiration_source": inspiration_source,
                "pitch": pitch,
                "target_audience": audience,
                "category": category,
                "pain_point": pain,
                "rank": RANK_MIN,
            }
        )
    return ideas


def generate_ideas(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce idea candidates for a list of normalized products.

    Each idea is assigned a mock ``rank`` integer in ``[RANK_MIN, RANK_MAX]``.
    Ranks vary across ideas in a deterministic, repeating pattern so consumers
    have a non-trivial signal to sort on.
    """
    ideas: list[dict[str, Any]] = []
    for product in products:
        ideas.extend(generate_ideas_for_product(product))
    for index, idea in enumerate(ideas):
        idea["rank"] = _rank_for_index(index)
    return ideas
