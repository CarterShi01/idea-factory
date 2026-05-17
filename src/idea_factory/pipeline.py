"""Pipeline orchestration: sources -> normalize -> ideate -> render."""

from __future__ import annotations

from dataclasses import dataclass

from . import ideate, normalize, render, sources


@dataclass
class PipelineResult:
    products: list[normalize.Product]
    ideas: list[ideate.Idea]


def run(limit: int | None = None) -> PipelineResult:
    raw = sources.collect(limit=limit)
    products = normalize.normalize(raw)
    ideas = ideate.generate(products)
    return PipelineResult(products=products, ideas=ideas)


def render_ideas(ideas: list[ideate.Idea], fmt: str) -> str:
    fmt = fmt.lower()
    if fmt == "json":
        return render.to_json(ideas)
    if fmt in {"md", "markdown"}:
        return render.to_markdown(ideas)
    raise ValueError(f"Unsupported format: {fmt!r}. Use 'json' or 'md'.")
