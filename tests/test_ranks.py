"""Round 2 alpha re-weighting tests (投资人复评严重度④).

round1: alpha over-weighted market_freshness and never weighted paid demand, so a
merely-trendy idea (#1) outranked one with a strong willingness-to-pay signal (#10).
These tests pin the corrected emphasis: strong pain + real payment beats fresh-only.
"""

from datetime import date

from idea_gen.ranks import DEFAULT_WEIGHTS, score_candidate
from idea_core.models import IdeaCandidate

TODAY = date(2026, 6, 15)


def _candidate(**kw) -> IdeaCandidate:
    base = dict(
        id="x",
        signal_id="s",
        source="external_event",
        title="t",
        pain="",
        solution="",
        target_user="developers",
        observed_on="2026-06-15",  # same date => decay is identical, isolates weights
        category=None,
    )
    base.update(kw)
    return IdeaCandidate(**base)


def test_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_payment_is_in_weights_and_freshness_demoted():
    # round1 prescription: payment is now a ranking input; freshness no longer dominant.
    assert DEFAULT_WEIGHTS["payment_signal"] >= 0.2
    assert DEFAULT_WEIGHTS["pain_intensity"] >= DEFAULT_WEIGHTS["market_freshness"]
    assert DEFAULT_WEIGHTS["payment_signal"] > DEFAULT_WEIGHTS["market_freshness"]


def test_paid_pain_outranks_fresh_only():
    # #10-like: strong, paid, sharp pain — but not riding a hot keyword.
    paid_pain = _candidate(
        title="ledger reconciliation for indie investors",
        pain="teams currently pay a freelancer and hire a consultant for this tedious manual work",
        solution="a focused reconciliation workflow",
    )
    # #1-like: rides every trend keyword but no paid signal and a weak pain.
    fresh_only = _candidate(
        title="local-first ai agent llm rag mcp copilot automation embedding vector",
        pain="people probably want this",
        solution="an llm agent",
    )
    a_paid = score_candidate(paid_pain, TODAY).alpha
    a_fresh = score_candidate(fresh_only, TODAY).alpha
    assert a_paid > a_fresh, (a_paid, a_fresh)


def test_unknown_factor_weight_defaults_to_zero():
    # score_candidate uses weights.get(name, 0.0); a partial weights dict is safe.
    c = _candidate(pain="manual tedious work")
    s = score_candidate(c, TODAY, weights={"pain_intensity": 1.0})
    assert s.alpha > 0.0
