"""Stage 4 -- generate idea candidates from signals (deliberately over-generate).

Two backends, same output type:

* :func:`generate` -- the offline **rule-based** default. Expands each signal into
  a few solution-shaped variants. Dumb on purpose: generation should be cheap and
  high-volume; the quality gate is downstream in ``idea_eval``.
* :func:`generate_llm` -- the **LLM (A) backend**. Renders one batched request per
  signal from ``config/llm/generate.json`` and runs it through any
  :class:`idea_core.llm.LLMBackend` (Tencent router / CC-handoff / mock). The
  batch-first contract means one ``complete()`` call covers all signals.

Both keep the same contract so the pipeline can switch between them with a flag.
"""

from __future__ import annotations

from typing import Callable

from idea_core.llm import LLMBackend, build_request, render_template
from idea_core.models import IdeaCandidate, Signal

from .dedup import _token_set, jaccard

# Rule path 是离线、零 token 的占位生成器：真 ideation 在 LLM 路径(generate_llm)。
# Round 1(投资人评审严重度①⑤)：删掉了写死的『一个 LLM 智能体，持续监控并自动处理:[痛点]』
# 换皮模板——它正是 mode collapse 的源头。改成几个**不同切入角度**的脚手架，并强制
# 每条带上 mechanism/why_now/mvp_week1 三要素的具体占位(虽弱于 LLM，但不再是换皮)。
# 每个角度给出 (angle 名, 切入说明, 第1周MVP 形态) —— 角度互不相同以保留多样性。
_RULE_ANGLES: list[tuple[str, str, str]] = [
    (
        "工作流嵌入",
        "把处理动作直接嵌进用户已有的工作流(IDE/邮箱/工单系统)，在痛点发生的那一刻就地给出可一键应用的结果，而不是另开一个新工具",
        "一个挂在现有工具上的插件/钩子，对单一高频场景给出可一键采纳的具体产出",
    ),
    (
        "数据/对账侧",
        "抓取并比对该场景两侧的结构化数据(如系统记录 vs 实际状态)，把人工核对变成可解释的差异清单",
        "一个读两份数据源、输出带证据的差异报告的脚本",
    ),
    (
        "决策辅助",
        "不替用户做，而是把分散信息聚成一页可对比的决策视图，缩短『我该怎么办』的判断时间",
        "一个汇总输入、产出一页对比/建议视图的只读看板",
    ),
]

_DEFAULT_USER = "软件开发者与独立创业者"


def _target_user(signal: Signal) -> str:
    cat = (signal.category or "").lower()
    if "dev" in cat or "ai" in cat or "software" in cat:
        return "开发者与技术型创始人"
    if "invest" in cat or "finance" in cat:
        return "管理 deal flow 的独立投资人"
    if "market" in cat or "content" in cat:
        return "独立营销人与创作者"
    return _DEFAULT_USER


def _rule_based_backend(signal: Signal) -> list[IdeaCandidate]:
    pain = signal.pain_statement or signal.title
    if not pain:
        return []
    user = _target_user(signal)
    candidates: list[IdeaCandidate] = []
    for idx, (angle, mechanism, mvp) in enumerate(_RULE_ANGLES):
        candidates.append(
            IdeaCandidate(
                id=f"{signal.id}-{idx}",
                signal_id=signal.id,
                source=signal.source,
                title=f"面向「{signal.title}」的{angle}方案"[:120],
                pain=pain,
                # No more 换皮模板：solution 体现该角度的具体机制，而非套『AI 智能体处理痛点』。
                solution=f"针对「{pain}」，采用「{angle}」路径：{mechanism}。",
                target_user=user,
                observed_on=signal.observed_on,
                confidence=signal.confidence,
                category=signal.category,
                trend_status=signal.trend_status,
                growth_speed=signal.growth_speed,
                mechanism=mechanism,
                why_now="离线规则路径未做竞品核查；请在 idea-eval（或 LLM 生成）阶段验证现有方案为何不足。",
                mvp_week1=mvp,
            )
        )
    return candidates


Backend = Callable[[Signal], list[IdeaCandidate]]


def generate(signals: list[Signal], backend: Backend = _rule_based_backend) -> list[IdeaCandidate]:
    candidates: list[IdeaCandidate] = []
    for signal in signals:
        candidates.extend(backend(signal))
    return candidates


# --- A: LLM generation backend -------------------------------------------


def _signal_fields(signal: Signal) -> dict:
    return {
        "title": signal.title,
        "pain_statement": signal.pain_statement,
        "category": signal.category or "",
        "source": signal.source,
        "observed_on": signal.observed_on,
    }


def _first(item: dict, *keys: str) -> str:
    for k in keys:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _candidates_from_response(signal: Signal, data: dict | None) -> list[IdeaCandidate]:
    if not data:
        return []
    # Prefer the requested {"candidates": [...]} shape, but tolerate a model that
    # returns a single idea object or a differently-keyed list.
    items = data.get("candidates")
    if not isinstance(items, list):
        items = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(items, list):
        items = [data] if any(k in data for k in ("title", "idea", "idea_name", "name")) else []

    out: list[IdeaCandidate] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = _first(item, "title", "idea_name", "name", "idea")
        if not title:
            continue
        out.append(
            IdeaCandidate(
                id=f"{signal.id}-{idx}",
                signal_id=signal.id,
                source=signal.source,
                title=title[:120],
                pain=_first(item, "pain", "problem", "pain_point") or signal.pain_statement,
                solution=_first(item, "solution", "description", "one_sentence_description"),
                target_user=_first(item, "target_user", "user", "audience") or _DEFAULT_USER,
                observed_on=signal.observed_on,
                confidence=signal.confidence,
                category=signal.category,
                trend_status=signal.trend_status,
                growth_speed=signal.growth_speed,
                # Round 1 真方案三要素：消化 VS 输出，落进 idea 字段。
                mechanism=_first(item, "mechanism", "how", "implementation", "tech"),
                why_now=_first(item, "why_now", "why_now_not_solved", "differentiation", "why"),
                mvp_week1=_first(item, "mvp_week1", "mvp", "week1", "first_week"),
            )
        )
    # VS 一次出多条 → 基本去重(同信号内近重的候选合并掉，保多样性)。
    return _dedupe_candidates(out)


# Round 1: Verbalized Sampling 一次给多条候选，需做基本去重后纳入候选池。
# 用与信号去重相同的词法 Jaccard(idea_gen.dedup)，对**同一信号**产出的候选去近重，
# 这样 mode-collapse 的换皮变体(措辞略改、实质相同)会被合并，保留真正不同角度的。
_CAND_DEDUP_THRESHOLD = 0.85


def _dedupe_candidates(candidates: list[IdeaCandidate]) -> list[IdeaCandidate]:
    """Drop near-duplicate candidates by lexical Jaccard over their text().

    Keeps insertion order; first occurrence wins. Operates within whatever list
    it's given (callers pass per-signal batches), so it never collapses ideas
    that legitimately came from different signals.
    """
    kept: list[IdeaCandidate] = []
    kept_tokens: list[set[str]] = []
    for c in candidates:
        tokens = _token_set(c.text())
        if any(jaccard(tokens, prev) >= _CAND_DEDUP_THRESHOLD for prev in kept_tokens):
            continue
        kept.append(c)
        kept_tokens.append(tokens)
    return kept


def generate_llm(signals: list[Signal], llm: LLMBackend, config: dict) -> list[IdeaCandidate]:
    """LLM (A) backend: one batched request per signal, a single complete() call.

    May raise ``idea_core.llm.PendingHandoff`` when the backend is CC-handoff and
    the response pack isn't ready yet -- callers should let it propagate to the CLI.
    """
    template = config.get("user_template", "")
    requests = [
        build_request(s.id, render_template(template, _signal_fields(s)), config)
        for s in signals
    ]
    responses = llm.complete(requests)
    by_id = {r.id: r for r in responses}

    candidates: list[IdeaCandidate] = []
    for s in signals:
        r = by_id.get(s.id)
        if r and r.ok:
            candidates.extend(_candidates_from_response(s, r.data))
    return candidates
