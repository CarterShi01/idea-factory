"""Stage 2b -- triage: hard red-line kills, cheap and before the LLM generate stage.

Per ``docs/design/pipeline-v2-plan.md`` §1/§5②: triage is where the *cheap*
money gets spent -- deterministic rule kills, no LLM call, no float score. A
red-line hit kills outright; there is no partial credit. This is deliberately
separate from ``idea_eval.evaluate``'s kill-gate (a *scored* rubric on the
survivors) -- triage's job is the small set of things that should never even
reach the (costlier) generate/rank/enrich/diligence stages, no matter how well
they'd otherwise score.

Two entry points, mirroring the two places triage bites in the funnel:

* :func:`triage_signals` -- before generate: hard-kills signals whose
  ``observed_on`` is older than ``max_months`` (cheat-on-money's "information
  over 24 months is stale" rule, applied as a *gate*, not a ranking discount --
  ``idea_gen.ranks``'s exponential decay is unchanged and still ranks the
  survivors by freshness).
* :func:`triage_candidates` -- after generate: hard-kills a candidate whose
  ``founder_fit`` factor (from :mod:`idea_core.factors`, the single source of
  truth shared with idea_eval) sits at the anti-fit floor -- a direction the
  founder profile itself flags as a bad fit (no channel, no moat, explicit
  anti-fit language), independent of how well the idea otherwise reads.

Already-seen / exact-duplicate signals are **not** re-implemented here --
:mod:`idea_gen.dedup` and (in dynamic mode) :mod:`idea_core.state`'s
``SeenStore`` already own that; triage only adds the two new red-lines.

Both functions return ``(kept, killed)`` where ``killed`` maps id -> reason
string, shaped for :func:`idea_core.ledger.log_impressions_bulk`.
"""

from __future__ import annotations

from datetime import date

from idea_factory.contract.models import Signal

STALE_24M = "stale_24m"

DEFAULT_MAX_MONTHS = 24
_AVG_MONTH_DAYS = 30.44  # good enough for a 24-month staleness gate


def _age_months(observed_on: str, today: date) -> float | None:
    try:
        observed = date.fromisoformat(observed_on)
    except (ValueError, TypeError):
        return None
    days = (today - observed).days
    if days < 0:
        return 0.0
    return days / _AVG_MONTH_DAYS


def triage_signals(
    signals: list[Signal],
    today: date,
    max_months: int = DEFAULT_MAX_MONTHS,
) -> tuple[list[Signal], dict[str, str]]:
    """Hard-kill signals older than ``max_months``. Returns ``(kept, {id: reason})``.

    A signal with an unparseable/blank ``observed_on`` (e.g. the ``1970-01-01``
    placeholder some fixtures use) is intentionally NOT killed here -- an
    unknown date is not evidence of staleness, and normalize.py's placeholder
    already gets ranked poorly by the age-based decay in ``idea_gen.ranks``.
    """
    kept: list[Signal] = []
    killed: dict[str, str] = {}
    for s in signals:
        age = _age_months(s.observed_on, today)
        if age is not None and age > max_months:
            killed[s.id] = STALE_24M
            continue
        kept.append(s)
    return kept, killed
