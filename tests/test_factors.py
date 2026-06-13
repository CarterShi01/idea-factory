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


def test_chinese_content_scores_nonzero():
    # A Chinese (LLM-generated style) candidate must score like its English peer,
    # not collapse to zero — otherwise the eval kill-gate kills everything Chinese.
    c = _candidate(
        title="面向独立开发者的 AI 智能体",
        pain="知识工作者浪费大量时间手动整理资料，效率低又繁琐",
        solution="一个带专有工作流集成的自动化助手",
        target_user="独立开发者与创始人",
    )
    scores = compute_factors(c)
    assert scores["pain_intensity"] > 0.0      # 浪费/手动/低效/繁琐
    assert scores["market_freshness"] > 0.1    # 智能体/自动化/助手
    assert scores["distribution_fit"] > 0.1    # 开发者/创始人
    assert all(0.0 <= v <= 1.0 for v in scores.values())
