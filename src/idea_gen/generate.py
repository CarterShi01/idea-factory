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
from idea_core.models import (
    CONFIDENCE_REAL,
    CONFIDENCE_SYNTHETIC,
    SOURCE_PERSONA,
    IdeaCandidate,
    Signal,
)

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
    # 源③人群等自带的目标用户优先(蒙语中老年 / 英语学习者……),别被 dev 默认值覆盖。
    if getattr(signal, "target_user", "").strip():
        return signal.target_user.strip()
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


def _source_guidance(signal: Signal, config: dict) -> str:
    """Per-source generation guidance (Round 3 三源融合, 投资人复评 #2).

    external_event / brain_inbox / pain_persona get *different* instructions so a
    brain-inbox idea isn't generated the same way as an external event. Falls back
    to the ``default`` entry for unknown sources / configs without the map.
    """
    table = config.get("source_guidance") or {}
    return table.get(signal.source) or table.get("default", "")


def _signal_fields(signal: Signal, config: dict | None = None) -> dict:
    return {
        "title": signal.title,
        "pain_statement": signal.pain_statement,
        "category": signal.category or "",
        "source": signal.source,
        "observed_on": signal.observed_on,
        "source_guidance": _source_guidance(signal, config or {}),
        # pipeline-v2 §5①:钱在流动的地方(招聘/成交/评论类源自带,其余源留空)。
        "money_trace": signal.money_trace or "(无明确付费痕迹)",
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
                # ff1 founder-fit: monopoly 三问落进 idea 字段（generate.json 强制要求）。
                why_only_me=_first(item, "why_only_me", "why_only_him", "founder_edge", "unfair_advantage", "moat_reason"),
                first_10_customers=_first(item, "first_10_customers", "first_customers", "first_ten_customers", "gtm", "first_10"),
                copy_fails_because=_first(item, "copy_fails_because", "yc_copy_fails", "why_copy_fails", "copy_fails"),
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

    Round 3(三源融合护城河,投资人复评 #2 + mission):
      * **per-source generation** — each signal's request carries a source-specific
        guidance block (external = timing/validated demand, brain = contrarian
        founder insight, persona = hypothesis needing corroboration);
      * **cross-source fusion** — signals from *different* sources that cluster onto
        the same theme (lexical Jaccard, no embeddings) get an extra fusion request
        whose candidates are tagged with ``fusion_sources``.

    Both the per-source requests and the fusion requests go into a SINGLE
    ``complete()`` call (batch-first contract).

    May raise ``idea_core.llm.PendingHandoff`` when the backend is CC-handoff and
    the response pack isn't ready yet -- callers should let it propagate to the CLI.
    """
    template = config.get("user_template", "")
    per_signal = [
        build_request(s.id, render_template(template, _signal_fields(s, config)), config)
        for s in signals
    ]

    # Build cross-source fusion requests (may be empty if no multi-source clusters).
    clusters = _cross_source_clusters(signals)
    fusion_cfg = config.get("fusion") or {}
    fusion_requests = _fusion_requests(clusters, fusion_cfg) if fusion_cfg else []

    responses = llm.complete(per_signal + fusion_requests)
    by_id = {r.id: r for r in responses}

    candidates: list[IdeaCandidate] = []
    for s in signals:
        r = by_id.get(s.id)
        if r and r.ok:
            candidates.extend(_candidates_from_response(s, r.data))

    # Fold in fusion candidates, tagged with their contributing source types.
    for cluster in clusters:
        r = by_id.get(_fusion_id(cluster))
        if r and r.ok:
            candidates.extend(_fusion_candidates_from_response(cluster, r.data))

    return candidates


# --- Round 3: cross-source fusion (mission 护城河) -------------------------

# 两条来自不同源的信号,词法 Jaccard ≥ 此阈值即视为指向同一主题,触发融合。
# 比候选去重的 0.85 低很多:融合要的是"沾边同主题"而非"近乎重复"。
_FUSION_THRESHOLD = 0.2


def _signal_tokens(s: Signal) -> set[str]:
    return _token_set(f"{s.title} {s.pain_statement} {s.category or ''}")


def _cross_source_clusters(signals: list[Signal]) -> list[list[Signal]]:
    """Group signals into themes that span ≥2 distinct sources (greedy, stdlib).

    Single-link clustering by lexical Jaccard over title+pain+category. A cluster
    is only returned if it draws on **more than one source type** — same-source
    near-dupes are already handled by dedup; fusion is specifically about
    cross-source chemistry (external timing + brain insight + persona pain).
    Deterministic: input order drives assignment.
    """
    tokens = [_signal_tokens(s) for s in signals]
    n = len(signals)
    cluster_of = [-1] * n
    clusters: list[list[int]] = []

    for i in range(n):
        if cluster_of[i] != -1:
            continue
        cluster_of[i] = len(clusters)
        members = [i]
        for j in range(i + 1, n):
            if cluster_of[j] != -1:
                continue
            if any(jaccard(tokens[j], tokens[k]) >= _FUSION_THRESHOLD for k in members):
                cluster_of[j] = len(clusters)
                members.append(j)
        clusters.append(members)

    out: list[list[Signal]] = []
    for members in clusters:
        sigs = [signals[k] for k in members]
        if len({s.source for s in sigs}) >= 2:
            out.append(sigs)
    return out


def _fusion_id(cluster: list[Signal]) -> str:
    return "fusion-" + "+".join(s.id for s in cluster)


def _fusion_sources(cluster: list[Signal]) -> list[str]:
    # Distinct source types, in first-seen order (stable).
    seen: list[str] = []
    for s in cluster:
        if s.source not in seen:
            seen.append(s.source)
    return seen


def _fusion_theme(cluster: list[Signal]) -> str:
    # A short human-readable theme label = the shortest title in the cluster.
    titles = [s.title for s in cluster if s.title]
    return min(titles, key=len) if titles else "(混合主题)"


def _fusion_bundle(cluster: list[Signal]) -> str:
    lines = []
    for s in cluster:
        lines.append(
            f"- [来源:{s.source}] 标题:{s.title}｜痛点:{s.pain_statement or '(无)'}"
            f"｜类别:{s.category or '-'}｜时间:{s.observed_on}"
        )
    return "\n".join(lines)


def _fusion_requests(clusters: list[list[Signal]], fusion_cfg: dict):
    template = fusion_cfg.get("user_template", "")
    requests = []
    for cluster in clusters:
        user = render_template(
            template,
            {"theme": _fusion_theme(cluster), "bundle": _fusion_bundle(cluster)},
        )
        requests.append(build_request(_fusion_id(cluster), user, fusion_cfg))
    return requests


def _fusion_candidates_from_response(cluster: list[Signal], data: dict | None) -> list[IdeaCandidate]:
    """Parse a fusion response, tagging each candidate with fusion_sources.

    The lead signal (cluster[0]) supplies id prefix / observed_on; confidence is
    forced to REAL only if at least one *non-persona* source backs the cluster,
    otherwise it stays SYNTHETIC (a fusion built purely on persona pain is still
    synthetic — the ≥1-real-corroboration rule).
    """
    lead = cluster[0]
    cands = _candidates_from_response(lead, data)
    sources = _fusion_sources(cluster)
    has_real = any(s.source != SOURCE_PERSONA for s in cluster)
    for idx, c in enumerate(cands):
        c.id = f"{_fusion_id(cluster)}-{idx}"
        c.fusion_sources = list(sources)
        c.confidence = CONFIDENCE_REAL if has_real else CONFIDENCE_SYNTHETIC
    return cands
