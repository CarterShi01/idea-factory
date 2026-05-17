"""End-to-end mock product-to-idea pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .export import export_json, export_markdown
from .generate import generate_ideas
from .normalize import normalize_products


def load_products(input_path: Path) -> list[dict[str, Any]]:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON list of product records in {input_path}, "
            f"got {type(data).__name__}."
        )
    return data


def run(input_path: Path, output_dir: Path) -> dict[str, Path]:
    raw = load_products(input_path)
    products = normalize_products(raw)
    ideas = generate_ideas(products)
    json_path = export_json(ideas, output_dir / "ideas.json")
    md_path = export_markdown(ideas, output_dir / "ideas.md")
    return {"json": json_path, "markdown": md_path}
