"""③generate 的跨源融合聚类(Round 3 三源融合护城河)。

来自**不同源**的信号(external timing + brain insight + persona pain)词法聚到同一
主题时,额外发一个融合请求——纯 stdlib 词法 Jaccard 单链聚类,零 embedding。
本模块只负责聚类 + 组请求(纯函数);响应解析在 .llm(那边有候选解析器)。
"""

from __future__ import annotations

from idea_factory.contract.models import Signal
from idea_factory.runtime.llm import build_request, render_template
from idea_factory.runtime.textsim import jaccard, tokens as _token_set

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
