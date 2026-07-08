"""Tests for idea_factory.stages.portfolio.bets -- the bet_memos.json outbound
boundary artifact (agent-service-plan.md §2.2)."""

from __future__ import annotations

import json
from datetime import date

from idea_factory.contract.models import KILL, PURSUE, REVIEW, Evaluation
from idea_factory.stages.portfolio.bets import build_bet_memos, write_bet_memos


def _idea(id_, **kw):
    base = {
        "id": id_, "source": "external_event", "pain": "痛点", "solution": "方案",
        "target_user": "目标用户", "why_now": "现在", "why_only_me": "只有我",
    }
    base.update(kw)
    return base


def test_build_bet_memos_excludes_killed_and_respects_top_n():
    evals = [
        Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90),
        Evaluation(idea_id="b", title="B", verdict=REVIEW, eval_score=80),
        Evaluation(idea_id="c", title="C", verdict=REVIEW, eval_score=70),
        Evaluation(idea_id="d", title="D", verdict=KILL, eval_score=10),
    ]
    ideas_by_id = {e.idea_id: _idea(e.idea_id) for e in evals}
    memos = build_bet_memos(evals, ideas_by_id, run_id="run-1", top_n=2)

    assert [m["bet_id"] for m in memos] == ["a", "b"]
    assert all(m["verdict"] != KILL for m in memos)


def test_bet_memo_shape_carries_hypothesis_evidence_and_experiment():
    exp = {"metric": "signups", "target": 10, "kill_below": 3,
           "horizon_days": 7, "budget_band": "0-500元"}
    e = Evaluation(
        idea_id="a", title="A", verdict=PURSUE, eval_score=90,
        riskiest_assumption="假设痛点真实", killer_objection="可能没人付费",
        experiment=exp, confidence="real",
        evidence=[{"kind": "competitor_pricing", "source_url": "u", "valid": True}],
        persona_objections=[{"persona": "p1", "objection": "看不懂"}],
    )
    idea = _idea("a")
    memos = build_bet_memos([e], {"a": idea}, run_id="run-1", top_n=3)
    m = memos[0]

    assert m["bet_id"] == "a"
    assert m["run_id"] == "run-1"
    assert m["hypothesis"] == {
        "pain": "痛点", "solution": "方案", "target_user": "目标用户",
        "why_now": "现在", "why_only_me": "只有我",
    }
    assert m["evidence"] == e.evidence
    assert m["riskiest_assumption"] == "假设痛点真实"
    assert m["killer_objection"] == "可能没人付费"
    assert m["persona_objections"] == e.persona_objections
    assert m["experiment"] == exp
    assert m["eval_score"] == 90
    assert m["confidence"] == "real"
    assert m["lineage_url"] == "/#/run/run-1/idea/a"


def test_write_bet_memos_writes_uniform_envelope(tmp_path):
    e = Evaluation(idea_id="a", title="A", verdict=PURSUE, eval_score=90)
    path = tmp_path / "bet_memos.json"
    write_bet_memos(
        [e], {"a": _idea("a")}, path,
        run_id="run-2026-07-08-1", week="2026-W28", today=date(2026, 7, 8), top_n=3,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 2
    assert data["stage"] == "bet_memos"
    assert data["run_id"] == "run-2026-07-08-1"
    assert data["week"] == "2026-W28"
    assert data["date"] == "2026-07-08"
    assert data["count"] == 1
    assert data["items"][0]["bet_id"] == "a"
