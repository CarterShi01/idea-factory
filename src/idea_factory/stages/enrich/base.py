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

agent-service-plan.md M-C2 (2026-07-08): the *mechanism* is decided --
``idea_factory.stages.recall.channels.vps_browser.fetch_via_browser`` (挂已
登录 Chrome), CC-handoff was rejected. What's still genuinely open, not just
missing targets: that helper returns recall-signal-shaped records (title/url/
category), while an ``Evidence`` needs ``keywords``(for the same per-candidate
match this module already does)/``source_date``/``numbers`` -- fields that
depend on the real target pages' structure, which the founder hasn't supplied
yet. Wiring this without that is a guess, not a fill-in-the-body task, so it's
intentionally left as a stub rather than a shape-mismatched fake wire.

Evidence with a ``source_date`` older than 24 months is fetched but marked
``valid=False`` (cheat-on-money's staleness rule) and does not count toward the
gate, but is still shown to the judge so it can say "this evidence is stale".
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from idea_factory.contract.models import (
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


