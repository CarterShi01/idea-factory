"""Idea generation.

Placeholder idea generator. The demo produces deterministic candidate ideas
by riffing on each normalized product's topics and tagline. A later version
will swap this for an LLM-backed generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .normalize import Product


@dataclass
class Idea:
    title: str
    pitch: str
    inspired_by: str
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "pitch": self.pitch,
            "inspired_by": self.inspired_by,
            "topics": list(self.topics),
        }


def _candidate_for(product: Product) -> Idea:
    primary_topic = product.topics[0] if product.topics else "general"
    title = f"{product.name} for {primary_topic.title()} Teams"
    pitch = (
        f"A focused take on \"{product.tagline}\" aimed at "
        f"{primary_topic} teams who need a sharper, opinionated workflow."
    )
    return Idea(
        title=title,
        pitch=pitch,
        inspired_by=product.name,
        topics=list(product.topics),
    )


def generate(products: list[Product]) -> list[Idea]:
    return [_candidate_for(p) for p in products if p.name]
