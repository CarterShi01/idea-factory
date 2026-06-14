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
    # ``scored`` may already be the diversity-selected digest (pipeline applies
    # ranks.select_diverse_top_n before calling); slicing to top_n is idempotent.
    digest = scored[:top_n]
    lines: list[str] = [
        f"# 创意工厂 — 每日候选（{today.isoformat()}）",
        "",
        f"展示前 {len(digest)} 条，按 alpha（因子加权 × 时间衰减）排序并做多样性去聚类（Non-Duplicate Ratio 优先，近重不挤占头部）。",
        "",
        "> 这些是 idea-gen 产出的**未筛选**候选；最终是否推进由 idea-eval 评估决定。",
        "",
    ]
    for rank, s in enumerate(digest, start=1):
        c = s.candidate
        synthetic = " ⚠️ 模拟" if c.confidence == "synthetic" else ""
        # Round 3:三源融合候选醒目标记,体现护城河(多源信号汇聚而成)。
        fusion = ""
        fsrc = getattr(c, "fusion_sources", None) or []
        if fsrc:
            fusion = f" 🔗 三源融合（{' + '.join(fsrc)}）"
        lines += [
            f"## {rank}. {c.title}  ·  alpha {s.alpha:.3f}{synthetic}{fusion}",
            "",
            f"- **痛点**：{c.pain}",
            f"- **方案**：{c.solution}",
        ]
        # Round 1 真方案三要素：仅在有内容时展示(rule/旧数据可能为空)。
        if getattr(c, "mechanism", ""):
            lines.append(f"- **机制**：{c.mechanism}")
        if getattr(c, "why_now", ""):
            lines.append(f"- **为何现在/现有方案不足**：{c.why_now}")
        if getattr(c, "mvp_week1", ""):
            lines.append(f"- **第 1 周 MVP**：{c.mvp_week1}")
        lines += [
            f"- **目标用户**：{c.target_user}",
            f"- **来源**：{c.source}（{c.observed_on}）· 衰减 {s.decay:.2f}",
            f"- **因子**：{_factor_line(s.factors)}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
