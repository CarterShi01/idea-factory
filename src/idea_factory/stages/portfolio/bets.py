"""⑦portfolio 的出向边界工件:``bet_memos.json``(agent-service-plan.md §2.2)。

投研部与 oc 之间只交换两种工件——这是"出"的那一半:一份机读的下注说明书,
每条 PURSUE/REVIEW 幸存者一条记录,收口假设 + 证据链 + 最危险假设 + 结构化实验
规格。oc 拿它派活/human-gate;idea-factory 不建议怎么拆卡、谁去做。

不经 :mod:`idea_factory.contract.artifacts` 的 STAGES 机制——bet_memos 不是漏斗
可续跑的边界(没有下游阶段读它作为输入),是 portfolio 阶段的一个*额外*产出,
地位等同 decision_memos.md / weekly_report.md,只是格式是机读 JSON 而非人读
markdown。信封形状仍照抄 §4 的统一信封,保持人工可读、可 diff。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from idea_factory.contract.models import KILL, Evaluation

SCHEMA_VERSION = 2


def build_bet_memos(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    run_id: str,
    top_n: int = 3,
) -> list[dict]:
    """Top ``top_n`` non-killed survivors (already diversified/sorted by the
    caller), each collapsed into one machine-readable bet memo record.
    """
    survivors = [e for e in evaluations if e.verdict != KILL][:top_n]
    memos = []
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        memos.append({
            "bet_id": e.idea_id,
            "run_id": run_id,
            "title": e.title,
            "verdict": e.verdict,
            "hypothesis": {
                "pain": idea.get("pain", ""),
                "solution": idea.get("solution", ""),
                "target_user": idea.get("target_user", ""),
                "why_now": idea.get("why_now", ""),
                "why_only_me": idea.get("why_only_me", ""),
            },
            "evidence": e.evidence,
            "riskiest_assumption": e.riskiest_assumption,
            "killer_objection": e.killer_objection,
            "persona_objections": e.persona_objections,
            "experiment": e.experiment,
            "eval_score": e.eval_score,
            "confidence": e.confidence,
            "lineage_url": f"/#/run/{run_id}/idea/{e.idea_id}",
        })
    return memos


def write_bet_memos(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    path: str | Path,
    *,
    run_id: str,
    week: str,
    today: date,
    top_n: int = 3,
) -> Path:
    path = Path(path)
    memos = build_bet_memos(evaluations, ideas_by_id, run_id, top_n=top_n)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "stage": "bet_memos",
        "run_id": run_id,
        "week": week,
        "date": today.isoformat(),
        "count": len(memos),
        "items": memos,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
