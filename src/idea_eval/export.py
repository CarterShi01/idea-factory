"""Write the evaluation results: machine-readable JSON + human decision memos."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .evaluate import KILL, PURSUE, REVIEW, Evaluation


def write_json(evaluations: list[Evaluation], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in evaluations]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _factor_line(factors: dict[str, float]) -> str:
    return " · ".join(f"{name} {value:.2f}" for name, value in factors.items())


def write_memos(
    evaluations: list[Evaluation],
    path: Path,
    today: date,
    top_n: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    survivors = [e for e in evaluations if e.verdict in (PURSUE, REVIEW)][:top_n]
    killed = [e for e in evaluations if e.verdict == KILL]

    lines: list[str] = [
        f"# Idea Factory — Decision Memos ({today.isoformat()})",
        "",
        f"{len(survivors)} ideas worth a look · {len(killed)} killed by the screen "
        f"· {len(evaluations)} evaluated.",
        "",
        "> Output of idea-eval: the kill-gate screen over idea-gen's candidates. "
        "A fatal flaw on a critical dimension (no real pain, or not solo-buildable) "
        "kills an idea outright.",
        "",
    ]
    for rank, e in enumerate(survivors, start=1):
        synthetic = " ⚠️ synthetic" if e.confidence == "synthetic" else ""
        lines += [
            f"## {rank}. {e.title}",
            "",
            f"- **Verdict**: {e.verdict.upper()} · score {e.eval_score:.0f}/100{synthetic}",
            f"- **Riskiest assumption**: {e.riskiest_assumption}",
            f"- **Cheap test (RAT)**: {e.cheap_experiment}",
        ]
        if e.risk_flags:
            lines.append(f"- **Risk flags**: {'; '.join(e.risk_flags)}")
        lines += [f"- **Factors**: {_factor_line(e.factors)}", ""]

    if killed:
        lines += ["---", "", "## Killed by the screen", ""]
        for e in killed:
            reason = (
                f"fatal flaw: {', '.join(e.killed_by)}"
                if e.killed_by
                else f"low score ({e.eval_score:.0f})"
            )
            lines.append(f"- ~~{e.title}~~ — {reason}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
