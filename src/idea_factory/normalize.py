"""Normalization.

Turn heterogeneous raw items into a uniform Product record that downstream
steps can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sources import RawItem


@dataclass
class Product:
    id: str
    name: str
    tagline: str
    topics: list[str] = field(default_factory=list)
    signal: int = 0
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "topics": list(self.topics),
            "signal": self.signal,
            "source": self.source,
        }


def normalize(items: list[RawItem]) -> list[Product]:
    products: list[Product] = []
    for item in items:
        payload = item.payload
        products.append(
            Product(
                id=f"{item.source}:{item.external_id}",
                name=str(payload.get("name", "")).strip(),
                tagline=str(payload.get("tagline", "")).strip(),
                topics=[str(t).lower() for t in payload.get("topics", [])],
                signal=int(payload.get("votes", 0) or 0),
                source=item.source,
            )
        )
    return products
