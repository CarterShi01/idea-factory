"""Normalize raw product records into a consistent structured form."""

from __future__ import annotations

from typing import Any


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        item = _clean_str(item).lower()
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def normalize_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of a single raw product record."""
    return {
        "id": _clean_str(raw.get("id")),
        "name": _clean_str(raw.get("name")),
        "tagline": _clean_str(raw.get("tagline")),
        "description": _clean_str(raw.get("description")),
        "url": _clean_str(raw.get("url")),
        "categories": _clean_list(raw.get("categories")),
        "target_users": _clean_list(raw.get("target_users")),
        "pain_points": _clean_list(raw.get("pain_points")),
        "launched_at": _clean_str(raw.get("launched_at")),
    }


def normalize_products(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize a list of raw product records, skipping entries with no name."""
    normalized: list[dict[str, Any]] = []
    for raw in raw_records:
        record = normalize_product(raw)
        if record["name"]:
            normalized.append(record)
    return normalized
