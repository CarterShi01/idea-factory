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


_VERDICT_ZH = {PURSUE: "推进", REVIEW: "待验证", KILL: "淘汰"}
_CONF_ZH = {"high": "高", "medium": "中", "low": "低"}


def _factor_line(factors: dict[str, float]) -> str:
    from idea_core.factors import label

    return " · ".join(f"{label(name)} {value:.2f}" for name, value in factors.items())


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
        f"# 创意工厂 — 决策备忘（{today.isoformat()}）",
        "",
        f"值得一看 {len(survivors)} 条 · 被筛掉 {len(killed)} 条 · 共评估 {len(evaluations)} 条。",
        "",
        "> idea-eval 的产出：对 idea-gen 候选的淘汰闸筛选。任一关键维度存在致命短板"
        "（没有真实痛点、或一人公司做不了）即直接淘汰。",
        "",
    ]
    for rank, e in enumerate(survivors, start=1):
        synthetic = " ⚠️ 模拟" if e.confidence == "synthetic" else ""
        judged = " · LLM 评委" if e.judged_by == "llm" else ""
        conf = f" · 置信度 {_CONF_ZH[e.judge_confidence]}" if e.judge_confidence in _CONF_ZH else ""
        demoted = " · ⚠️ 低置信度自动降级到待验证" if e.confidence_demoted else ""
        lines += [
            f"## {rank}. {e.title}",
            "",
            f"- **结论**：{_VERDICT_ZH.get(e.verdict, e.verdict)} · 得分 {e.eval_score:.0f}/100{conf}{synthetic}{judged}{demoted}",
        ]
        if e.critique:
            lines.append("- **对抗式批判**：")
            for obj in e.critique:
                lines.append(f"  - {obj}")
            if e.doomed_assumption:
                lines.append(f"  - *若被证伪即垮的假设*：{e.doomed_assumption}")
        if e.judge_rebuttal:
            lines.append(f"- **评委回应**：{e.judge_rebuttal}")
        if e.killer_objection:
            lines.append(f"- **最致命质疑**：{e.killer_objection}")
        lines += [
            f"- **最危险假设**：{e.riskiest_assumption}",
            f"- **最小验证**：{e.cheap_experiment}",
        ]
        if e.risk_flags:
            lines.append(f"- **风险提示**：{'；'.join(e.risk_flags)}")
        lines += [f"- **因子**：{_factor_line(e.factors)}", ""]

    if killed:
        lines += ["---", "", "## 被淘汰", ""]
        for e in killed:
            reason = (
                f"致命短板：{'、'.join(e.killed_by)}"
                if e.killed_by
                else f"得分过低（{e.eval_score:.0f}）"
            )
            lines.append(f"- ~~{e.title}~~ — {reason}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
