"""Output rendering for the demo pipeline."""

from __future__ import annotations

import json
from typing import Any

from .ideate import Idea


def to_json(ideas: list[Idea]) -> str:
    payload: list[dict[str, Any]] = [idea.to_dict() for idea in ideas]
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(ideas: list[Idea]) -> str:
    if not ideas:
        return "# Idea Candidates\n\n_No ideas generated._\n"

    lines: list[str] = ["# Idea Candidates", ""]
    for idea in ideas:
        lines.append(f"## {idea.title}")
        lines.append("")
        lines.append(idea.pitch)
        lines.append("")
        lines.append(f"- Inspired by: {idea.inspired_by}")
        if idea.topics:
            lines.append(f"- Topics: {', '.join(idea.topics)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
