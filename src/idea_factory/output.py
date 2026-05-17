"""Write pipeline results to disk as JSON and/or Markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, products: list[dict[str, Any]], ideas: list[dict[str, Any]]) -> Path:
    payload = {"products": products, "ideas": ideas}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_markdown(path: Path, products: list[dict[str, Any]], ideas: list[dict[str, Any]]) -> Path:
    lines: list[str] = ["# Idea Factory Demo Run", "", "## Products", ""]
    for product in products:
        categories = ", ".join(product["categories"]) or "—"
        lines.append(f"- **{product['name']}** — {product['tagline']} _({categories})_")
    lines.extend(["", "## Idea Candidates", ""])
    for idea in ideas:
        lines.append(f"### {idea['title']}")
        lines.append(f"- Inspired by: {idea['inspired_by']}")
        lines.append(f"- Category: {idea['category']}")
        lines.append(f"- Target user: {idea['target_user']}")
        lines.append(f"- Hypothesis: {idea['hypothesis']}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
