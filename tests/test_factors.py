from idea_core.factors import (
    FACTORS,
    competition_density,
    compute_factors,
    distribution_fit,
    market_freshness,
    moat_signal,
    pain_intensity,
)
from idea_core.models import CONFIDENCE_SYNTHETIC, IdeaCandidate


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


# --- Round 2: discrimination (投资人复评严重度② "这不是打分是开关") ----------


def test_factors_are_not_binary_switches():
    """The investor's core complaint: factors clustered at extremes (1.0/0.1).

    Build a spread of candidates and assert each factor produces several
    distinct values, not just {0.1, 1.0}.
    """
    candidates = [
        _candidate(title="ai", pain="manual slow", solution="proprietary data moat",
                   target_user="developers"),
        _candidate(title="another todo chatbot clone", pain="missing", solution="generic wrapper",
                   target_user="people"),
        _candidate(title="vector rag mcp agent copilot automation", pain="tedious expensive",
                   solution="deep integration network effect dataset vertical", target_user="founders"),
        # one medium-complexity build (single med hit) -> mid build_cost
        _candidate(title="compliance helper", pain="manual repetitive error-prone",
                   solution="adds an audit log", target_user="engineers"),
        # one heavy build -> low build_cost
        _candidate(title="hardware marketplace", pain="costly", solution="blockchain supply chain",
                   target_user="builders"),
        # one clean solo build -> high build_cost
        _candidate(title="cli linter", pain="slow", solution="a small script", target_user="indie"),
        # one merely-busy (single light crowded hit) -> mid competition_density
        _candidate(title="invoice dashboard for indie investors", pain="manual tedious",
                   solution="a focused reconciliation view", target_user="investors"),
    ]
    for name, fn in FACTORS.items():
        values = {round(fn(c), 3) for c in candidates}
        assert len(values) >= 3, f"factor {name} is near-binary: {values}"


def test_moat_grades_by_distinct_types():
    none = _candidate(solution="a simple ui tweak")
    one = _candidate(solution="built on proprietary data")
    many = _candidate(solution="proprietary dataset plus strong network effects and deep integration")
    assert moat_signal(none) < moat_signal(one) < moat_signal(many)
    assert moat_signal(none) >= 0.1  # floor, not zero
    assert moat_signal(many) > 0.5


def test_competition_density_grades_crowdedness():
    open_space = _candidate(title="vertical ledger reconciliation for indie investors")
    busy = _candidate(title="ai assistant dashboard summarizer")
    commodity = _candidate(title="another todo app clone generic wrapper")
    assert competition_density(open_space) > competition_density(busy) > competition_density(commodity)


def test_market_freshness_spreads_not_pinned_to_one():
    cold = _candidate(title="ledger reconciliation")
    warm = _candidate(title="ai automation tool")
    hot = _candidate(title="ai agent llm rag mcp copilot automation embedding vector")
    assert market_freshness(cold) < market_freshness(warm) < market_freshness(hot)
    assert market_freshness(hot) < 1.0  # never snaps flat to 1.0 from keywords


def test_distribution_fit_weights_target_user():
    in_target = _candidate(target_user="developers and indie founders", pain="x")
    off_target = _candidate(target_user="hospital nurses", pain="x")
    assert distribution_fit(in_target) > distribution_fit(off_target)


# --- Round 2: pain evidence (投资人复评严重度① 伪痛点/无证据痛点) ------------


def test_pain_evidence_willingness_to_pay_lifts_score():
    paid = _candidate(pain="teams currently pay a freelancer and hate the manual work")
    unpaid = _candidate(pain="teams do manual work")
    assert pain_intensity(paid) > pain_intensity(unpaid)


def test_speculative_pain_is_discounted():
    real = _candidate(pain="developers waste hours on tedious manual reconciliation")
    imagined = _candidate(
        pain="imagine users might want to judge priority by voice tone, would be nice to have"
    )
    assert pain_intensity(imagined) < pain_intensity(real)


def test_vague_evidenceless_pain_floored_low():
    vague = _candidate(pain="people probably need better tools someday")
    assert pain_intensity(vague) <= 0.2


def test_synthetic_pain_discounted_without_corroboration():
    text = "users do manual tedious work"
    real = _candidate(pain=text)
    synth = _candidate(pain=text, confidence=CONFIDENCE_SYNTHETIC)
    assert pain_intensity(synth) < pain_intensity(real)
    # but a paid signal rescues a synthetic pain (≥1 real corroboration rule)
    synth_paid = _candidate(
        pain="users currently pay for this manual tedious work",
        confidence=CONFIDENCE_SYNTHETIC,
    )
    assert pain_intensity(synth_paid) > pain_intensity(synth)
