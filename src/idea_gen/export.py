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
    from idea_core.factors import label

    return " · ".join(f"{label(name)} {value:.2f}" for name, value in factors.items())


def write_markdown(
    scored: list[ScoredCandidate],
    path: Path,
    today: date,
    top_n: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# 创意工厂 — 每日候选（{today.isoformat()}）",
        "",
        f"共 {len(scored)} 条候选，按 alpha（因子加权 × 时间衰减、含多样性）排序，取前 {min(top_n, len(scored))} 条。",
        "",
        "> 这些是 idea-gen 产出的**未筛选**候选；最终是否推进由 idea-eval 评估决定。",
        "",
    ]
    for rank, s in enumerate(scored[:top_n], start=1):
        c = s.candidate
        synthetic = " ⚠️ 模拟" if c.confidence == "synthetic" else ""
        lines += [
            f"## {rank}. {c.title}  ·  alpha {s.alpha:.3f}{synthetic}",
            "",
            f"- **痛点**：{c.pain}",
            f"- **方案**：{c.solution}",
            f"- **目标用户**：{c.target_user}",
            f"- **来源**：{c.source}（{c.observed_on}）· 衰减 {s.decay:.2f}",
            f"- **因子**：{_factor_line(s.factors)}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
