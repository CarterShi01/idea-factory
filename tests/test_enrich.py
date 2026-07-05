"""Tests for idea_eval.enrich — fixture-backed evidence fetchers + the gate."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from idea_core.models import EVIDENCE_COMPETITOR_PRICING, EVIDENCE_HIRING, IdeaCandidate
from idea_eval import enrich

REF_DATE = date(2026, 7, 5)


def _idea(id_, *, pain="", solution="", target_user="", first_10_customers="") -> dict:
    return IdeaCandidate(
        id=id_, signal_id="s1", source="external_event", title="t",
        pain=pain, solution=solution, target_user=target_user, observed_on="2026-06-01",
        first_10_customers=first_10_customers,
    ).to_dict()


def test_default_fixtures_match_stripe_reconciliation_idea():
    idea = _idea(
        "stripe1",
        pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账",
        solution="自动对账工具",
        first_10_customers="在相关 SaaS 创始人群里发帖",
    )
    cand = IdeaCandidate(**{k: idea[k] for k in idea if k in IdeaCandidate.__dataclass_fields__})
    evs = enrich.fetch_all(cand, REF_DATE)
    kinds = {e.kind for e in evs}
    assert EVIDENCE_COMPETITOR_PRICING in kinds
    assert EVIDENCE_HIRING in kinds
    assert all(e.valid for e in evs)

    ready, missing = enrich.evidence_gate(idea, evs)
    assert ready is True
    assert missing == []


def test_niche_persona_idea_with_no_market_data_stays_awaiting_evidence():
    idea = _idea(
        "mongolian1",
        pain="蒙语母语者缺少能听懂说得出的蒙语语音助手",
        solution="蒙语语音助手",
        target_user="内蒙古蒙语母语中老年人",
        first_10_customers="",
    )
    cand = IdeaCandidate(**{k: idea[k] for k in idea if k in IdeaCandidate.__dataclass_fields__})
    evs = enrich.fetch_all(cand, REF_DATE)
    assert evs == []  # no fixture covers this niche -> no evidence at all

    ready, missing = enrich.evidence_gate(idea, evs)
    assert ready is False
    assert set(missing) == {"paying_proof", "competitor_pricing", "reach_path"}


def test_reach_path_satisfied_by_first_10_customers_even_without_evidence():
    idea = _idea(
        "custom1",
        pain="等保合规和日常安全运维靠人工整理证据、出报告",
        solution="自动取证工具",
        first_10_customers="通过安全云销售朋友引荐企业客户",
    )
    cand = IdeaCandidate(**{k: idea[k] for k in idea if k in IdeaCandidate.__dataclass_fields__})
    evs = enrich.fetch_all(cand, REF_DATE)
    ready, missing = enrich.evidence_gate(idea, evs)
    assert ready is True
    assert "reach_path" not in missing


def test_stale_evidence_marked_invalid_and_does_not_satisfy_gate(tmp_path):
    fixture_dir = tmp_path / "evidence"
    fixture_dir.mkdir()
    (fixture_dir / "pricing.jsonl").write_text(
        json.dumps({
            "keywords": ["测试关键词"], "source_url": "https://old.example.com",
            "source_date": "2020-01-01", "summary": "过期证据", "numbers": {"price": 9},
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (fixture_dir / "hiring.jsonl").write_text("", encoding="utf-8")
    (fixture_dir / "deals.jsonl").write_text("", encoding="utf-8")

    idea = _idea("stale1", pain="测试关键词场景", solution="工具", first_10_customers="渠道X")
    cand = IdeaCandidate(**{k: idea[k] for k in idea if k in IdeaCandidate.__dataclass_fields__})
    fetchers = enrich.default_fetchers(fixture_dir)
    evs = enrich.fetch_all(cand, REF_DATE, fetchers=fetchers)
    assert len(evs) == 1
    assert evs[0].valid is False  # >24 months old

    ready, missing = enrich.evidence_gate(idea, evs)
    assert ready is False
    assert "competitor_pricing" in missing  # stale evidence doesn't count


def test_live_mode_is_a_stubbed_noop():
    idea = _idea("live1", pain="独立 SaaS 创始人浪费大量时间手动把 Stripe 回款与发票对账")
    cand = IdeaCandidate(**{k: idea[k] for k in idea if k in IdeaCandidate.__dataclass_fields__})
    assert enrich.fetch_all(cand, REF_DATE, live=True) == []


def test_enrich_ideas_batch():
    ideas = [
        _idea("a", pain="客服团队浪费时间手动回答重复工单", first_10_customers="HN 发帖"),
        _idea("b", pain="蒙语母语者缺少语音助手", target_user="内蒙古蒙语母语中老年人"),
    ]
    evidence_by_id, gate_by_id = enrich.enrich_ideas(ideas, REF_DATE)
    assert gate_by_id["a"][0] is True
    assert gate_by_id["b"][0] is False
    assert len(evidence_by_id["a"]) > 0
    assert evidence_by_id["b"] == []
