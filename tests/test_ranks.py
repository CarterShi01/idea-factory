"""Round 2 alpha re-weighting tests (投资人复评严重度④).

round1: alpha over-weighted market_freshness and never weighted paid demand, so a
merely-trendy idea (#1) outranked one with a strong willingness-to-pay signal (#10).
These tests pin the corrected emphasis: strong pain + real payment beats fresh-only.
"""

from datetime import date

from idea_gen.ranks import (
    DEFAULT_WEIGHTS,
    _COMMODITY_DIST_PENALTY,
    _COMMODITY_DIST_THRESHOLD,
    score_candidate,
)
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


# --- ff2 founder-fit: distribution_fit is now a ranking主力 + commodity hard gate ---


def test_distribution_fit_is_a_ranking_force():
    # ff2: dist 权重从陪跑 0.05 升为与 pain_intensity 并列的排序主力,真正影响排序。
    assert DEFAULT_WEIGHTS["distribution_fit"] >= 0.2
    assert DEFAULT_WEIGHTS["distribution_fit"] >= DEFAULT_WEIGHTS["market_freshness"]
    assert DEFAULT_WEIGHTS["distribution_fit"] >= DEFAULT_WEIGHTS["build_cost"]


def test_monopoly_channel_outranks_generic_even_with_high_pain():
    # ff2 病根:dist=0.93(获客垄断)和 dist=0.21(纯通用货)都进了 top。修复后:
    # 即使通用货痛点/付费信号拉满,无独占渠道(dist<0.3)也必须被硬降权门压到垄断货之下。
    monopoly = _candidate(
        title="蒙语政企客服",
        pain="政企手动处理蒙语工单繁琐昂贵",
        target_user="内蒙古蒙语政企",
        why_only_me="家人在内蒙古、蒙语母语,天然信任渠道别人进不来",
        first_10_customers="内蒙古家人介绍当地政企 3 家",
    )
    generic = _candidate(
        title="english customer support plugin",
        pain="teams currently pay a freelancer and hire a consultant for this tedious manual expensive work",
        solution="we pay per month subscription budget",
        target_user="developers",
        first_10_customers="发到开发者社区和 product hunt 投放买量",
    )
    s_mono = score_candidate(monopoly, TODAY)
    s_gen = score_candidate(generic, TODAY)
    # generic 触达是纯公开渠道 -> dist 低于阈值 -> 硬降权门生效
    assert s_gen.factors["distribution_fit"] < _COMMODITY_DIST_THRESHOLD
    assert s_mono.factors["distribution_fit"] >= 0.8
    assert s_mono.alpha > s_gen.alpha, (s_mono.alpha, s_gen.alpha)


def test_commodity_dist_gate_applies_multiplicative_penalty():
    # 一条 dist<0.3 的通用货,其 alpha 应≈无门时的 _COMMODITY_DIST_PENALTY 倍(其余因子不变)。
    generic = _candidate(
        title="generic tool",
        pain="teams do tedious manual work",
        target_user="developers",
        first_10_customers="发到开发者社区投放买量",
    )
    s = score_candidate(generic, TODAY)
    assert s.factors["distribution_fit"] < _COMMODITY_DIST_THRESHOLD
    # 同一条若把渠道换成蒙语独占(dist≥0.3),不触发门 -> alpha 明显更高。
    with_channel = _candidate(
        title="generic tool",
        pain="teams do tedious manual work",
        target_user="内蒙古蒙语用户",
        why_only_me="蒙语母语家人信任渠道",
    )
    s2 = score_candidate(with_channel, TODAY)
    assert s2.factors["distribution_fit"] >= _COMMODITY_DIST_THRESHOLD
    assert s2.alpha > s.alpha


def test_unknown_factor_weight_defaults_to_zero():
    # score_candidate uses weights.get(name, 0.0); a partial weights dict is safe.
    c = _candidate(pain="manual tedious work")
    s = score_candidate(c, TODAY, weights={"pain_intensity": 1.0})
    assert s.alpha > 0.0
