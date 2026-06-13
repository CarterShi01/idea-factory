"""Stage 7 -- write the ranked candidates out as JSON and a daily Markdown report.

The JSON is the machine-readable hand-off to ``idea-evl`` (it carries every
candidate plus its factor scores). The Markdown is the human-facing "daily
N ideas" digest, echoing the IdeaBrowser "idea of the day" format from the
research.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from idea_core.models import ScoredCandidate


def write_json(scored: list[ScoredCandidate], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [s.to_dict() for s in scored]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _factor_line(factors: dict[str, float]) -> str:
    return " · ".join(f"{name} {value:.2f}" for name, value in factors.items())


def write_markdown(
    scored: list[ScoredCandidate],
    path: Path,
    today: date,
    top_n: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# Idea Factory — Daily Candidates ({today.isoformat()})",
        "",
        f"Top {min(top_n, len(scored))} of {len(scored)} generated candidates, "
        "ranked by alpha (factor-weighted, time-decayed) with diversity pressure.",
        "",
        "> These are *unscreened* candidates from idea-factory. Final go/no-go "
        "screening is idea-evl's job.",
        "",
    ]
    for rank, s in enumerate(scored[:top_n], start=1):
        c = s.candidate
        synthetic = " ⚠️ synthetic" if c.confidence == "synthetic" else ""
        lines += [
            f"## {rank}. {c.title}  ·  alpha {s.alpha:.3f}{synthetic}",
            "",
            f"- **Pain**: {c.pain}",
            f"- **Solution**: {c.solution}",
            f"- **Target user**: {c.target_user}",
            f"- **Source**: {c.source} ({c.observed_on}) · decay {s.decay:.2f}",
            f"- **Factors**: {_factor_line(s.factors)}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
