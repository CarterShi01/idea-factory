"""源③ 合成痛点(LLM 步,批处理,真实信号佐证才放行)。

流程:select_segments 选出高价值细分人群 → 对每个人群,把源①里与其 evidence_topics
相关的真实信号作为上下文,让 LLM 批量推断痛点 → 用 crosscheck.corroborate 判断每条
痛点是否被真实信号佐证:
  · 被佐证 → confidence="synthetic_grounded"(放行)
  · 未佐证 → confidence="synthetic_only"(降权,kill-gate 应进一步处理)

走 idea_core.llm 的批处理后端(腾讯 router / CC 手动 / mock);零碎切,一批人群一个请求集。
"""

from __future__ import annotations

import json

from idea_core.llm import build_request, render_template

from ..crosscheck import corroborate


def _ground_signals(seg, real_records: list[dict], limit: int = 8) -> list[dict]:
    topics = [t.lower() for t in getattr(seg, "evidence_topics", [])]
    out = []
    for r in real_records:
        hay = (str(r.get("title", "")) + str(r.get("category", "")) + str(r.get("pain", ""))).lower()
        if any(t in hay for t in topics):
            out.append(r)
    return out[:limit]


def synthesize_pains(segments, real_records, llm, config: dict) -> list[dict]:
    """对选中人群批量合成痛点,返回 raw 信号 dict 列表(可直接进 normalize)。"""
    template = config.get("user_template", "")
    requests = []
    grounding: dict[str, list[dict]] = {}
    for seg in segments:
        grounded = _ground_signals(seg, real_records)
        grounding[seg.id] = grounded
        user = render_template(
            template,
            {
                "persona": seg.label,
                "axes": json.dumps(seg.axes, ensure_ascii=False),
                "signals": "\n".join(f"- {r.get('title', '')}" for r in grounded) or "(暂无直接相关的真实信号)",
            },
        )
        requests.append(build_request(seg.id, user, config))

    responses = {r.id: r for r in llm.complete(requests)}
    out: list[dict] = []
    for seg in segments:
        r = responses.get(seg.id)
        if not (r and r.ok and r.data):
            continue
        for p in r.data.get("pains", []):
            summary = (p.get("summary") or "").strip()
            if not summary:
                continue
            corrob = corroborate(summary, real_records)
            out.append(
                {
                    "source": "pain_persona",
                    "source_name": "persona_llm",
                    "title": summary,
                    "pain": summary,
                    "text": p.get("verbatim", summary),
                    "target_user": seg.label,
                    "category": seg.id,
                    "confidence": "synthetic_grounded" if corrob.real_hits else "synthetic_only",
                    "corroborated": corrob.real_hits > 0,
                    "evidence_real_hits": corrob.real_hits,
                }
            )
    return out
