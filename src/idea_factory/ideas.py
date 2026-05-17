"""Generate startup idea candidates from normalized product records.

The demo uses a simple template; later versions can swap in an LLM call.
"""

from __future__ import annotations

from typing import Any


def generate_ideas(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce one idea candidate per input product."""
    ideas: list[dict[str, Any]] = []
    for product in products:
        primary_category = product["categories"][0] if product["categories"] else "general"
        ideas.append(
            {
                "title": f"A team-focused take on {product['name']}",
                "inspired_by": product["name"],
                "category": primary_category,
                "hypothesis": (
                    f"If {product['name']} works for individuals, a version aimed at small "
                    f"teams in the {primary_category} space could capture an underserved segment."
                ),
                "target_user": f"Small teams interested in {primary_category}",
            }
        )
    return ideas
