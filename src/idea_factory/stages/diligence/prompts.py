"""⑥diligence 的 prompt 字段装配 + trace 落盘(critique 与 judge 共用)。"""

from __future__ import annotations

import json

from idea_factory.contract.models import Evaluation


def _evidence_block(evidence: list[dict]) -> str:
    """Render a candidate's fetched evidence (enrich stage) for the critique/judge
    prompt. Empty when enrich never ran or found nothing -- critique/judge must not
    invent evidence in that case (the prompt says so explicitly).
    """
    if not evidence:
        return "（暂无证据 —— 未跑证据门,或跑了但没查到任何相关证据。不要假装有证据支撑,也不要因为没证据就直接判死;倾向 review。）"
    lines = []
    for ev in evidence:
        stale = " ⚠️已过24月失效" if not ev.get("valid", True) else ""
        lines.append(
            f"- id={ev.get('id', '')} [{ev.get('kind', '')}] {ev.get('summary', '')} "
            f"{ev.get('numbers', {})}（{ev.get('source_date', '')}）{stale}"
        )
    return "\n".join(lines)


def _survivor_fields(e: Evaluation, idea: dict) -> dict:
    return {
        "title": e.title,
        "pain": idea.get("pain", ""),
        "solution": idea.get("solution", ""),
        "target_user": idea.get("target_user", ""),
        "factors": json.dumps(e.factors, ensure_ascii=False),
        "confidence": e.confidence,
        # 来源:让 critique/judge 按来源分叉——external_event(英文HN市场机会)不该用
        # 独占/护城河标尺去杀,pain_persona/brain_inbox 才按 founder 独占审(中英混合)。
        "source": idea.get("source", ""),
        # ff1 founder-fit: surface the generator's monopoly claims so the critic/judge
        # can attack them directly ("你说只有你能做,但这条用不上蒙语/没有那条引荐").
        # render_template ignores unused placeholders, so existing prompts are unaffected.
        "why_only_me": idea.get("why_only_me", ""),
        "first_10_customers": idea.get("first_10_customers", ""),
        "copy_fails_because": idea.get("copy_fails_because", ""),
        # 只在 enrich/apply 跑过后才非空;render_template 对未用到的占位符安全。
        "evidence_block": _evidence_block(e.evidence),
    }


def _critique_block(e: Evaluation) -> str:
    if not e.critique and not e.critique_killer:
        return "（无对抗式批判 — 直接评估）"
    lines = [f"- {o}" for o in e.critique]
    if e.critique_killer:
        lines.append(f"最致命：{e.critique_killer}")
    if e.doomed_assumption:
        lines.append(f"若被证伪即垮的假设：{e.doomed_assumption}")
    return "\n".join(lines)


def _log_trace_batch(trace_data_dir, trace_run_id, stage, requests, responses, prompt_version):
    """Thin alias to the shared runtime helper (kept for critique/judge callers)."""
    from idea_factory.runtime.llm import log_trace_batch

    log_trace_batch(trace_data_dir, trace_run_id, stage, requests, responses, prompt_version)
