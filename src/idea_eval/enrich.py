"""idea_eval.enrich -- Stage 5: give each rank-survivor a real-world evidence chain.

Per ``docs/design/pipeline-v2-plan.md`` §5⑤: this is where the system stops
asking an LLM to judge on vibes and starts handing it something to cite. Three
fetchers (pricing / hiring / deals), one **evidence gate**: a candidate only
counts as "ready for diligence" once it has ≥1 paying-proof evidence, ≥1
competitor-pricing evidence, and a reach-path (either evidence-backed or the
generator's own ``first_10_customers`` claim).

Offline by default, fixture-backed (``data/raw/fixtures/evidence/*.jsonl``),
matched to a candidate by simple keyword containment against ``candidate.text()``
-- the same lexical-matching style the rest of this codebase already uses
(persona/hn fixtures, factor vocab). ``live=True`` is deliberately stubbed to a
no-op: wiring a real fetch (hitting competitor pricing pages / job boards /
marketplace listings over the network) is an explicit, founder-approved
follow-up per CLAUDE.md's "no real external API calls without approval" hard
rule -- this module ships the interface + gate + fixtures now, the live
fetcher later.

Evidence with a ``source_date`` older than 24 months is fetched but marked
``valid=False`` (cheat-on-money's staleness rule) and does not count toward the
gate, but is still shown to the judge so it can say "this evidence is stale".
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from idea_core.models import (
    EVIDENCE_COMPETITOR_PRICING,
    EVIDENCE_DEAL,
    EVIDENCE_HIRING,
    EVIDENCE_PAYING_PROOF,
    EVIDENCE_REACH_PATH,
    Evidence,
    IdeaCandidate,
)

MAX_EVIDENCE_AGE_MONTHS = 24
_AVG_MONTH_DAYS = 30.44
_FIXTURE_DIR_DEFAULT = Path("data/raw/fixtures/evidence")

# Evidence kinds that count as "someone is already paying for this today".
_PAYING_PROOF_KINDS = {EVIDENCE_HIRING, EVIDENCE_DEAL, EVIDENCE_PAYING_PROOF}


def _age_months(source_date_str: str, today: date) -> float | None:
    try:
        d = date.fromisoformat(source_date_str)
    except (ValueError, TypeError):
        return None
    days = (today - d).days
    return max(0.0, days / _AVG_MONTH_DAYS)


def _is_valid(source_date_str: str, today: date) -> bool:
    age = _age_months(source_date_str, today)
    return age is not None and age <= MAX_EVIDENCE_AGE_MONTHS


def _matches(text: str, keywords: list) -> bool:
    text = text.lower()
    return any(str(kw).lower() in text for kw in keywords)


@runtime_checkable
class Fetcher(Protocol):
    kind: str

    def fetch(self, candidate: IdeaCandidate, today: date, live: bool = False) -> list[Evidence]:
        ...


class _FixtureFetcher:
    """Base for the fixture-backed fetchers below.

    ``live=True`` is a no-op (returns ``[]``) -- see module docstring. Matching
    is a plain keyword-containment scan over ``candidate.text()``, mirroring
    ``idea_core.factors``'s vocabulary-matching style.
    """

    kind = ""
    fixture_name = ""

    def __init__(self, fixture_dir: str | Path = _FIXTURE_DIR_DEFAULT):
        self.fixture_dir = Path(fixture_dir)

    def _records(self) -> list[dict]:
        path = self.fixture_dir / self.fixture_name
        if not path.exists():
            return []
        out: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def fetch(self, candidate: IdeaCandidate, today: date, live: bool = False) -> list[Evidence]:
        if live:
            return []  # stubbed: real network fetch needs explicit founder approval
        text = candidate.text()
        out: list[Evidence] = []
        for i, rec in enumerate(self._records()):
            if not _matches(text, rec.get("keywords", [])):
                continue
            source_date = rec.get("source_date", "")
            out.append(
                Evidence(
                    id=f"{self.kind}-{candidate.id}-{i}",
                    candidate_id=candidate.id,
                    kind=self.kind,
                    source_url=rec.get("source_url", ""),
                    source_date=source_date,
                    fetched_at=today.isoformat(),
                    summary=rec.get("summary", ""),
                    numbers=rec.get("numbers", {}) or {},
                    valid=_is_valid(source_date, today),
                )
            )
        return out


class PricingFetcher(_FixtureFetcher):
    """Competitor pricing pages -- 有名字有价格的方案。"""

    kind = EVIDENCE_COMPETITOR_PRICING
    fixture_name = "pricing.jsonl"


class HiringFetcher(_FixtureFetcher):
    """Relevant job postings -- 公司愿意为这个痛点付薪,最强付费证据之一。"""

    kind = EVIDENCE_HIRING
    fixture_name = "hiring.jsonl"


class DealsFetcher(_FixtureFetcher):
    """Marketplace/service transaction records -- 有人已经在人肉解决并收钱。"""

    kind = EVIDENCE_DEAL
    fixture_name = "deals.jsonl"


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


# --- evidence gate (plan §5④) -----------------------------------------------


def evidence_gate(idea: dict, evidences: list[Evidence]) -> tuple[bool, list[str]]:
    """3-condition gate. Returns ``(ready, missing)``; ``missing`` lists which
    condition(s) failed -- feeds the ``awaiting_evidence`` reason / retry queue.
    """
    valid = [e for e in evidences if e.valid]
    has_paying = any(e.kind in _PAYING_PROOF_KINDS for e in valid)
    has_pricing = any(e.kind == EVIDENCE_COMPETITOR_PRICING for e in valid)
    reach_path_ok = bool((idea.get("first_10_customers") or "").strip()) or any(
        e.kind == EVIDENCE_REACH_PATH for e in valid
    )

    missing: list[str] = []
    if not has_paying:
        missing.append("paying_proof")
    if not has_pricing:
        missing.append("competitor_pricing")
    if not reach_path_ok:
        missing.append("reach_path")
    return (not missing), missing


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
