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
_JUDGE_DIM_ZH = {
    "pain_real": "真实痛",
    "solo_buildable": "一人可做",
    "reachable": "可触达",
    "defensible": "防御性",
    "timing": "时机",
}


def _judge_score_line(scores: dict[str, float]) -> str:
    return " · ".join(f"{_JUDGE_DIM_ZH[k]} {scores[k]:.2f}" for k in _JUDGE_DIM_ZH if k in scores)


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
        if e.judge_scores:
            lines.append(f"- **评委五维**：{_judge_score_line(e.judge_scores)}")
        lines += [f"- **生成侧因子**：{_factor_line(e.factors)}", ""]

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


# --- pipeline-v2: weekly report (docs/design/pipeline-v2-plan.md §8) --------
#
# Additive: does NOT replace write_memos/decision_memos.md above (still the
# default daily output). This is the north-star artifact -- top few survivors
# only, each armed with its clickable evidence chain and a smoke-test package,
# meant to be read at most weekly. Only meaningful once a run went through
# idea_eval.enrich (require_evidence=True) -- without evidence, every idea
# lands in the "待补证据" tier, which is itself the correct, honest signal.

_TIER_ZH = {PURSUE: "本周就测", REVIEW: "待验证复核", KILL: "淘汰"}
_EVIDENCE_KIND_ZH = {
    "paying_proof": "付费证据", "competitor_pricing": "竞品定价",
    "reach_path": "触达路径", "hiring": "招聘证据", "deal": "成交证据",
}


def _tier_of(e: Evaluation) -> str:
    if e.verdict == REVIEW and e.evidence_missing:
        return "待补证据"
    return _TIER_ZH.get(e.verdict, e.verdict)


def _evidence_lines(evidence: list[dict]) -> list[str]:
    if not evidence:
        return ["  (暂无证据 —— 需先跑 idea-eval --require-evidence)"]
    lines = []
    for ev in evidence:
        kind = _EVIDENCE_KIND_ZH.get(ev.get("kind", ""), ev.get("kind", ""))
        stale = "" if ev.get("valid", True) else " ⚠️ 已过 24 月,视为失效"
        url = ev.get("source_url", "")
        summary = ev.get("summary", "")
        date_ = ev.get("source_date", "")
        lines.append(f"  - [{kind}]({url}) {summary}（{date_}）{stale}")
    return lines


def _smoke_test_block(idea: dict, e: Evaluation) -> list[str]:
    """A rule-composed draft smoke-test package -- a scaffold to fill in by hand,
    not an LLM-authored plan (that's a documented follow-up, see plan §5⑤/⑦).
    """
    channel = (idea.get("first_10_customers") or "").strip() or "(未指定 —— 补 first_10_customers)"
    price_hint = "; ".join(
        f"{ev.get('numbers', {}).get('price')}{ev.get('numbers', {}).get('currency', '')}"
        for ev in e.evidence
        if ev.get("kind") == "competitor_pricing" and ev.get("numbers", {}).get("price") is not None
    ) or "(参考同类定价证据自定)"
    return [
        "- **48h 测试包**（草稿,需人工补全）：",
        f"  - 渠道：{channel}",
        f"  - 参考定价：{price_hint}",
        "  - 预测：待人工填写(如『7 天内 10 个邮箱』),测完用 `idea-eval retro` 回填实际数字",
    ]


def write_weekly_report(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    path: Path,
    week: str,
    top_n: int = 3,
) -> None:
    """Write the §8-format weekly report: top ``top_n`` survivors only, each
    with its evidence chain + a smoke-test scaffold. Ranked pursue-first, then
    review, by score -- mirrors ``_sort``'s ordering.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    survivors = [e for e in evaluations if e.verdict != KILL][:top_n]

    lines: list[str] = [
        f"# 创意工厂 — 本周候选（{week}）",
        "",
        f"本周共 {len(survivors)} 条(上限 {top_n})。每条都附钱的证据链——没有证据链的字段会明确标出,"
        "不是编出来的。",
        "",
    ]
    for rank, e in enumerate(survivors, start=1):
        idea = ideas_by_id.get(e.idea_id, {})
        lines += [
            f"## 本周 #{rank}：{e.title}　　tier: {_tier_of(e)}",
            "",
            f"- **痛点**：{idea.get('pain', '')}（源：{idea.get('source', '')}，{idea.get('observed_on', '')}）",
            f"- **方案**：{idea.get('solution', '')}",
            "- **钱的证据链**：",
        ]
        lines += _evidence_lines(e.evidence)
        lines.append(f"- **前 10 个客户在哪**：{idea.get('first_10_customers', '') or '(未填写)'}")
        lines.append(f"- **最危险假设**：{e.riskiest_assumption}")
        lines += _smoke_test_block(idea, e)
        if e.risk_flags:
            lines.append(f"- **评委理由**：{'；'.join(e.risk_flags)}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
