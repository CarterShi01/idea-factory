"""Tests for evaluate.enforce_citation — judge output must cite real evidence_ids."""

from __future__ import annotations

from idea_eval.evaluate import KILL, PURSUE, REVIEW, Evaluation, enforce_citation


def _eval(idea_id, verdict, judged_by="llm", evidence=None, judge_reasons=None) -> Evaluation:
    return Evaluation(
        idea_id=idea_id, title=idea_id, verdict=verdict, eval_score=30.0,
        judged_by=judged_by, evidence=evidence or [], judge_reasons=judge_reasons or [],
    )


_EVIDENCE = [{"id": "ev1", "kind": "competitor_pricing"}, {"id": "ev2", "kind": "hiring"}]


def test_demotes_llm_kill_with_evidence_but_no_citation():
    e = _eval("a", KILL, evidence=_EVIDENCE, judge_reasons=[{"claim": "没有护城河", "evidence_ids": []}])
    out = enforce_citation([e])
    assert out[0].verdict == REVIEW
    assert out[0].citation_demoted is True
    assert any("未引用任何证据编号" in f for f in out[0].risk_flags)


def test_keeps_llm_kill_when_citation_is_valid():
    e = _eval("a", KILL, evidence=_EVIDENCE, judge_reasons=[{"claim": "竞品才卖29美元", "evidence_ids": ["ev1"]}])
    out = enforce_citation([e])
    assert out[0].verdict == KILL
    assert out[0].citation_demoted is False


def test_strips_hallucinated_evidence_ids():
    e = _eval("a", KILL, evidence=_EVIDENCE, judge_reasons=[{"claim": "x", "evidence_ids": ["ev1", "ev-does-not-exist"]}])
    out = enforce_citation([e])
    # the real id is kept, the hallucinated one is dropped
    assert out[0].judge_reasons[0]["evidence_ids"] == ["ev1"]
    assert out[0].verdict == KILL  # still counts as cited because ev1 is valid


def test_hallucinated_only_citation_counts_as_uncited_and_demotes():
    e = _eval("a", KILL, evidence=_EVIDENCE, judge_reasons=[{"claim": "x", "evidence_ids": ["ev-fake"]}])
    out = enforce_citation([e])
    assert out[0].judge_reasons[0]["evidence_ids"] == []
    assert out[0].verdict == REVIEW
    assert out[0].citation_demoted is True


def test_no_evidence_at_all_never_demotes():
    # Nothing to cite -> not held against the kill.
    e = _eval("a", KILL, evidence=[], judge_reasons=[{"claim": "x", "evidence_ids": []}])
    out = enforce_citation([e])
    assert out[0].verdict == KILL
    assert out[0].citation_demoted is False


def test_rule_only_kill_is_never_touched_even_with_evidence():
    e = _eval("a", KILL, judged_by="rule", evidence=_EVIDENCE, judge_reasons=[])
    out = enforce_citation([e])
    assert out[0].verdict == KILL
    assert out[0].citation_demoted is False


def test_pursue_and_review_are_never_touched():
    p = _eval("a", PURSUE, evidence=_EVIDENCE, judge_reasons=[])
    r = _eval("b", REVIEW, evidence=_EVIDENCE, judge_reasons=[])
    out = enforce_citation([p, r])
    by_id = {e.idea_id: e for e in out}
    assert by_id["a"].verdict == PURSUE
    assert by_id["b"].verdict == REVIEW
    assert not by_id["a"].citation_demoted and not by_id["b"].citation_demoted
