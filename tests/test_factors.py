from idea_core.factors import FACTORS, compute_factors, pain_intensity
from idea_core.models import IdeaCandidate


def _candidate(**kw) -> IdeaCandidate:
    base = dict(
        id="x",
        signal_id="s",
        source="external_event",
        title="t",
        pain="",
        solution="",
        target_user="",
        observed_on="2026-06-01",
        category=None,
    )
    base.update(kw)
    return IdeaCandidate(**base)


def test_all_factors_in_unit_range():
    c = _candidate(
        title="ai agent for developers",
        pain="developers waste hours manually doing tedious repetitive work",
        solution="an llm agent with proprietary workflow integration",
        target_user="developers and founders",
    )
    scores = compute_factors(c)
    assert set(scores) == set(FACTORS)
    assert all(0.0 <= v <= 1.0 for v in scores.values())


def test_pain_intensity_rewards_sharper_pain():
    sharp = _candidate(pain="expensive manual tedious slow frustrating waste of hours")
    mild = _candidate(pain="a nice to have improvement")
    assert pain_intensity(sharp) > pain_intensity(mild)


def test_factors_are_pure():
    c = _candidate(pain="manual tedious work")
    assert compute_factors(c) == compute_factors(c)
