"""Source collection.

Placeholder collector for the first demo. Real implementations will fetch
from Product Hunt or similar public sources; for now this returns a small
in-memory sample so the rest of the pipeline can run end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawItem:
    """A raw, source-shaped record before normalization."""

    source: str
    external_id: str
    payload: dict[str, Any] = field(default_factory=dict)


_SAMPLE_ITEMS: list[RawItem] = [
    RawItem(
        source="sample",
        external_id="ph-001",
        payload={
            "name": "Lumen Notes",
            "tagline": "AI meeting notes that summarize on the fly",
            "topics": ["productivity", "ai", "meetings"],
            "votes": 412,
        },
    ),
    RawItem(
        source="sample",
        external_id="ph-002",
        payload={
            "name": "Quill Inbox",
            "tagline": "Triages your email with one keyboard shortcut",
            "topics": ["productivity", "email"],
            "votes": 289,
        },
    ),
    RawItem(
        source="sample",
        external_id="ph-003",
        payload={
            "name": "Patchwork",
            "tagline": "Drop-in observability for indie SaaS",
            "topics": ["devtools", "observability"],
            "votes": 174,
        },
    ),
]


def collect(limit: int | None = None) -> list[RawItem]:
    """Return raw items from configured sources.

    The demo returns a fixed sample. A future version will replace this with
    real HTTP calls to public launch feeds.
    """
    items = list(_SAMPLE_ITEMS)
    if limit is not None:
        items = items[:limit]
    return items
