"""Export idea candidates to JSON and Markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def export_json(ideas: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ideas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def export_markdown(ideas: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["# Idea Candidates", ""]
    if not ideas:
        lines.append("_No ideas were generated._")
    else:
        lines.append(f"Total candidates: **{len(ideas)}**")
        lines.append("")
        for i, idea in enumerate(ideas, start=1):
            lines.append(f"## {i}. {idea.get('source_product_name', 'Unknown')}")
            lines.append("")
            lines.append(f"- **Pitch:** {idea.get('pitch', '')}")
            lines.append(f"- **Target audience:** {idea.get('target_audience', '')}")
            lines.append(f"- **Category:** {idea.get('category', '')}")
            lines.append(f"- **Pain point:** {idea.get('pain_point', '')}")
            inspiration = idea.get("inspiration_source", "")
            if inspiration:
                lines.append(f"- **Inspiration source:** {inspiration}")
            source_id = idea.get("source_product_id", "")
            if source_id:
                lines.append(f"- **Source product id:** `{source_id}`")
            lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
