"""⑤enrich 的批量执行:对 rank 幸存者逐条取证 + 过证据门。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from idea_factory.contract.models import Evidence, IdeaCandidate

from .base import _FIXTURE_DIR_DEFAULT, Fetcher, evidence_gate
from .deals import DealsFetcher
from .hiring import HiringFetcher
from .pricing import PricingFetcher

def default_fetchers(fixture_dir: str | Path = _FIXTURE_DIR_DEFAULT) -> tuple[Fetcher, ...]:
    return (
        PricingFetcher(fixture_dir),
        HiringFetcher(fixture_dir),
        DealsFetcher(fixture_dir),
    )


def fetch_all(
    candidate: IdeaCandidate,
    today: date,
    fetchers: tuple[Fetcher, ...] | None = None,
    live: bool = False,
) -> list[Evidence]:
    fetchers = fetchers if fetchers is not None else default_fetchers()
    out: list[Evidence] = []
    for f in fetchers:
        out.extend(f.fetch(candidate, today, live=live))
    return out


def _candidate_from_idea_dict(idea: dict) -> IdeaCandidate:
    """ideas.json entries are ScoredCandidate.to_dict() -- drop the extra
    factors/alpha/decay keys and reconstruct the IdeaCandidate for text()/id.
    """
    fields = IdeaCandidate.__dataclass_fields__
    kwargs = {k: idea[k] for k in idea if k in fields}
    return IdeaCandidate(**kwargs)


def enrich_ideas(
    ideas: list[dict],
    today: date,
    fetchers: tuple[Fetcher, ...] | None = None,
    live: bool = False,
) -> tuple[dict[str, list[Evidence]], dict[str, tuple[bool, list[str]]]]:
    """Enrich a batch of idea dicts (as read from ideas.json).

    Returns ``(evidence_by_id, gate_by_id)`` where ``gate_by_id[id]`` is the
    ``(ready, missing)`` tuple from :func:`evidence_gate`.
    """
    fetchers = fetchers if fetchers is not None else default_fetchers()
    evidence_by_id: dict[str, list[Evidence]] = {}
    gate_by_id: dict[str, tuple[bool, list[str]]] = {}
    for idea in ideas:
        cand = _candidate_from_idea_dict(idea)
        evs = fetch_all(cand, today, fetchers=fetchers, live=live)
        evidence_by_id[idea["id"]] = evs
        gate_by_id[idea["id"]] = evidence_gate(idea, evs)
    return evidence_by_id, gate_by_id
