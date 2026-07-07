"""③generate 的 LLM 路径:每信号一请求 + 跨源融合请求,单次 batch complete()。

Round 3(三源融合护城河,投资人复评 #2 + mission):
  * **per-source generation** — each signal's request carries a source-specific
    guidance block (external = timing/validated demand, brain = contrarian
    founder insight, persona = hypothesis needing corroboration);
  * **cross-source fusion** — clustering lives in .fusion; response parsing here.

May raise ``PendingHandoff`` when the backend is CC-handoff and the response
pack isn't ready yet -- callers let it propagate to the CLI.
"""

from __future__ import annotations

from idea_factory.contract.models import (
    CONFIDENCE_REAL,
    CONFIDENCE_SYNTHETIC,
    SOURCE_PERSONA,
    IdeaCandidate,
    Signal,
)
from idea_factory.runtime.llm import LLMBackend, build_request, render_template
from idea_factory.runtime.textsim import jaccard, tokens as _token_set

from .fusion import _cross_source_clusters, _fusion_id, _fusion_requests, _fusion_sources
from .rule import _DEFAULT_USER

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


def generate_llm(
    signals: list[Signal], llm: LLMBackend, config: dict,
    trace_data_dir=None, trace_run_id: str | None = None,
) -> list[IdeaCandidate]:
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

    May raise ``idea_factory.runtime.llm.PendingHandoff`` when the backend is CC-handoff and
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

    all_requests = per_signal + fusion_requests
    responses = llm.complete(all_requests)
    by_id = {r.id: r for r in responses}

    from idea_factory.runtime.llm import log_trace_batch
    log_trace_batch(trace_data_dir, trace_run_id, "generate", all_requests, by_id,
                    config.get("step", "generate"))

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



# --- fusion response parsing (clustering lives in .fusion) ---


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
