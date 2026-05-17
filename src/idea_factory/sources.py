"""Source collection.

Placeholder collector that returns a small in-memory sample of product launches.
A future version will fetch from Product Hunt or similar public sources.
"""

from __future__ import annotations

from typing import Any


SAMPLE_PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "FocusFlow",
        "tagline": "Block distractions and stay in deep work.",
        "description": "A desktop app that silences notifications and tracks focused work sessions.",
        "categories": ["productivity", "wellness"],
        "url": "https://example.com/focusflow",
    },
    {
        "name": "ChefMate AI",
        "tagline": "Turn what's in your fridge into dinner.",
        "description": "Mobile assistant that suggests recipes based on ingredients you already own.",
        "categories": ["food", "ai"],
        "url": "https://example.com/chefmate",
    },
    {
        "name": "PaperPilot",
        "tagline": "Read research papers 10x faster.",
        "description": "Browser extension that summarizes academic PDFs and extracts key findings.",
        "categories": ["research", "ai", "education"],
        "url": "https://example.com/paperpilot",
    },
]


def collect_products() -> list[dict[str, Any]]:
    """Return raw product records from the configured sources.

    For the demo this returns a hardcoded sample so the pipeline runs offline.
    """
    return [dict(p) for p in SAMPLE_PRODUCTS]
