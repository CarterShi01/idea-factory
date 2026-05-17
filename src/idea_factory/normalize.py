"""Normalize raw product records into a consistent shape."""

from __future__ import annotations

from typing import Any


def normalize_products(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce raw product dicts into a uniform structured record."""
    normalized: list[dict[str, Any]] = []
    for item in raw:
        normalized.append(
            {
                "name": str(item.get("name", "")).strip(),
                "tagline": str(item.get("tagline", "")).strip(),
                "description": str(item.get("description", "")).strip(),
                "categories": [
                    c.strip().lower()
                    for c in item.get("categories", [])
                    if isinstance(c, str) and c.strip()
                ],
                "url": str(item.get("url", "")).strip(),
            }
        )
    return normalized
