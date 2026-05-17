"""Generate mock startup idea candidates from normalized product records.

This is intentionally rule-based and offline. Each product can spawn one or
more idea candidates derived from its categories, target users, and pain
points. No external API calls.
"""

from __future__ import annotations

from typing import Any

TEMPLATES = [
    "An AI copilot for {audience} that eliminates {pain}, inspired by {name}.",
    "A vertical {category} tool focused on {audience}, taking {name}'s approach further.",
    "A community-driven take on {name} that crowdsources solutions to {pain}.",
]


def _first_or(values: list[str], default: str) -> str:
    return values[0] if values else default


def generate_ideas_for_product(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Produce idea candidates for a single normalized product."""
    name = product.get("name") or "an unnamed product"
    audience = _first_or(product.get("target_users", []), "early adopters")
    category = _first_or(product.get("categories", []), "general")
    pains = product.get("pain_points") or ["an unmet user need"]

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
                "source_product_id": product.get("id", ""),
                "source_product_name": name,
                "pitch": pitch,
                "target_audience": audience,
                "category": category,
                "pain_point": pain,
            }
        )
    return ideas


def generate_ideas(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce idea candidates for a list of normalized products."""
    ideas: list[dict[str, Any]] = []
    for product in products:
        ideas.extend(generate_ideas_for_product(product))
    return ideas
