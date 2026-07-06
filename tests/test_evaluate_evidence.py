"""Tests for idea_eval.evaluate's pipeline-v2 evidence-aware additions:
apply_evidence / enforce_evidence_grounding / enforce_forced_distribution.
"""

from __future__ import annotations

from idea_factory.contract.models import KILL, PURSUE, REVIEW, Evaluation
from idea_factory.stages.diligence.apply import apply_evidence
from idea_factory.stages.diligence.enforce import (
    enforce_evidence_grounding,
    enforce_forced_distribution,
)


def _eval(idea_id, verdict, score=70.0) -> Evaluation:
    return Evaluation(idea_id=idea_id, title=idea_id, verdict=verdict, eval_score=score)


def test_apply_evidence_attaches_evidence_and_gate():
    evals = [_eval("a", PURSUE), _eval("b", PURSUE)]
    evidence_by_id = {"a": [{"kind": "competitor_pricing", "valid": True}]}
    gate_by_id = {"a": (True, []), "b": (False, ["paying_proof", "competitor_pricing"])}
    apply_evidence(evals, evidence_by_id, gate_by_id)

    assert evals[0].evidence_ready is True
    assert evals[0].evidence == [{"kind": "competitor_pricing", "valid": True}]
    assert evals[1].evidence_ready is False
    assert evals[1].evidence_missing == ["paying_proof", "competitor_pricing"]


def test_apply_evidence_accepts_evidence_objects_with_to_dict():
    class FakeEvidence:
        def to_dict(self):
            return {"kind": "hiring"}

    evals = [_eval("a", PURSUE)]
    apply_evidence(evals, {"a": [FakeEvidence()]}, {"a": (True, [])})
    assert evals[0].evidence == [{"kind": "hiring"}]


def test_enforce_evidence_grounding_demotes_ungrounded_pursue():
    evals = [_eval("a", PURSUE), _eval("b", PURSUE)]
    apply_evidence(evals, {}, {"a": (True, []), "b": (False, ["paying_proof"])})
    out = enforce_evidence_grounding(evals)
    by_id = {e.idea_id: e for e in out}

    assert by_id["a"].verdict == PURSUE
    assert by_id["a"].evidence_demoted is False

    assert by_id["b"].verdict == REVIEW
    assert by_id["b"].evidence_demoted is True
    assert any("无真实证据支撑" in f for f in by_id["b"].risk_flags)


def test_enforce_evidence_grounding_never_touches_kill_or_already_review():
    evals = [_eval("a", KILL), _eval("b", REVIEW)]
    apply_evidence(evals, {}, {"a": (False, ["x"]), "b": (False, ["y"])})
    out = enforce_evidence_grounding(evals)
    by_id = {e.idea_id: e for e in out}
    assert by_id["a"].verdict == KILL
    assert by_id["b"].verdict == REVIEW
    assert not by_id["a"].evidence_demoted
    assert not by_id["b"].evidence_demoted  # only PURSUE gets demoted; REVIEW is already the safe lane


def test_forced_distribution_caps_pursue_fraction():
    # 4 pursue, 1 kill = 5 total, cap at 50% = 2 pursue may survive.
    evals = [
        _eval("a", PURSUE, score=90),
        _eval("b", PURSUE, score=80),
        _eval("c", PURSUE, score=70),
        _eval("d", PURSUE, score=60),
        _eval("e", KILL, score=10),
    ]
    out = enforce_forced_distribution(evals, max_pursue_frac=0.5)
    pursue_ids = {e.idea_id for e in out if e.verdict == PURSUE}
    assert pursue_ids == {"a", "b"}  # top 2 by score survive
    demoted = [e for e in out if e.idea_id in ("c", "d")]
    assert all(e.verdict == REVIEW and e.forced_downgrade for e in demoted)
    assert next(e for e in out if e.idea_id == "e").verdict == KILL  # kill untouched


def test_forced_distribution_noop_when_under_cap():
    evals = [_eval("a", PURSUE), _eval("b", KILL), _eval("c", KILL)]
    out = enforce_forced_distribution(evals, max_pursue_frac=0.5)
    assert next(e for e in out if e.idea_id == "a").verdict == PURSUE
    assert not next(e for e in out if e.idea_id == "a").forced_downgrade


def test_forced_distribution_empty_batch_noop():
    assert enforce_forced_distribution([]) == []
