"""Round 3 tests — three-source fusion, per-source guidance, diversity Top-N,
and the rebuilt build_cost / moat_signal factors (投资人复评 #1/#2/#3 + mission 护城河).

All offline: a MockBackend canned responder stands in for the LLM. Kept in a
dedicated file so it doesn't collide with the other round's test edits.
"""

from datetime import date

from idea_core.factors import build_cost, moat_signal
from idea_core.llm import LLMResponse, MockBackend
from idea_core.models import IdeaCandidate, ScoredCandidate
from idea_gen.generate import _fusion_candidates_from_response, generate_llm
from idea_gen.normalize import normalize_record
from idea_gen.ranks import select_diverse_top_n

REF_DATE = date(2026, 6, 13)


def _sig(source_name, source, title, pain, category=None):
    rec = {"source_name": source_name, "title": title, "pain": pain}
    if category:
        rec["category"] = category
    s = normalize_record(rec)
    s.source = source  # force the high-level source type for the test
    return s


def _candidate(**kw) -> IdeaCandidate:
    base = dict(
        id="x", signal_id="s", source="external_event", title="t",
        pain="", solution="", target_user="", observed_on="2026-06-01", category=None,
    )
    base.update(kw)
    return IdeaCandidate(**base)


# --- ① build_cost / moat distribution (投资人复评 #1) ----------------------


def test_build_cost_is_not_all_one():
    """The #1 complaint: build_cost pinned at 1.0 for everyone."""
    clean = _candidate(title="cli linter", solution="a tiny local script")
    one_integration = _candidate(title="stripe reconciler", solution="reads the stripe api and diffs invoices")
    many = _candidate(
        title="ai trainer",
        solution="fine-tune a self-hosted model, integrate stripe github slack, ship ios and android apps",
    )
    bc_clean = build_cost(clean)
    bc_one = build_cost(one_integration)
    bc_many = build_cost(many)
    # spread, not a flat 1.0
    assert bc_clean < 1.0
    assert bc_clean > bc_one > bc_many
    assert bc_many >= 0.05  # floored, never zero


def test_build_cost_penalizes_model_and_platform():
    base = _candidate(solution="a focused web tool")
    model = _candidate(solution="a focused web tool that fine-tunes a custom model")
    multi = _candidate(solution="a focused tool shipped as ios and android and chrome extension")
    assert build_cost(model) < build_cost(base)
    assert build_cost(multi) < build_cost(base)


def test_moat_clears_floor_on_prose_descriptions():
    """The complaint: moat ~0.1 for everyone. Prose moats must now register."""
    bare = _candidate(solution="a simple ui tweak")
    flywheel = _candidate(solution="it gets smarter with use as a data flywheel compounds")
    multi = _candidate(
        solution="a data flywheel that improves with use, network effects as more users join, "
        "and deep domain know-how"
    )
    assert moat_signal(bare) < moat_signal(flywheel) < moat_signal(multi)
    assert moat_signal(flywheel) > 0.1  # cleared the floor (was stuck at 0.1)
    assert moat_signal(multi) > 0.5


# --- ② per-source guidance + cross-source fusion (投资人复评 #2 + mission) --


def test_per_source_guidance_is_injected():
    captured = {}

    def responder(req):
        captured[req.id] = req.user
        return LLMResponse(id=req.id, data={"candidates": []})

    ext = _sig("hn", "external_event", "竞品刚发布新功能", "创始人追竞品变更很费时")
    brain = _sig("manual", "brain_inbox", "一个反共识的小工具", "我觉得没人这么干但可能对")
    cfg = {
        "user_template": "{source_guidance}",
        "source_guidance": {
            "external_event": "EXTERNAL-TIMING",
            "brain_inbox": "BRAIN-CONTRARIAN",
            "default": "DEFAULT",
        },
    }
    generate_llm([ext, brain], MockBackend(responder), cfg)
    assert "EXTERNAL-TIMING" in captured[ext.id]
    assert "BRAIN-CONTRARIAN" in captured[brain.id]


def test_cross_source_fusion_emits_tagged_candidate():
    ext = _sig("hn", "external_event", "手动对账 Stripe 回款很痛",
               "创始人手动对账 Stripe 回款很费时", "fintech-dev")
    brain = _sig("manual", "brain_inbox", "自动对账 Stripe 回款的工具",
                 "对账 Stripe 回款重复劳动", "fintech-dev")

    def responder(req):
        if req.id.startswith("fusion-"):
            return LLMResponse(id=req.id, data={"candidates": [
                {"title": "三源融合对账方案", "pain": "对账痛", "solution": "s",
                 "mechanism": "m", "why_now": "w", "mvp_week1": "v", "target_user": "创始人"},
            ]})
        return LLMResponse(id=req.id, data={"candidates": [
            {"title": f"普通-{req.id}", "pain": "p", "solution": "s",
             "mechanism": "m", "why_now": "w", "mvp_week1": "v", "target_user": "u"},
        ]})

    cfg = {"user_template": "{title}",
           "fusion": {"system": "fuse", "user_template": "{theme} {bundle}"}}
    cands = generate_llm([ext, brain], MockBackend(responder), cfg)
    fused = [c for c in cands if c.fusion_sources]
    assert fused, "expected at least one fusion candidate"
    assert set(fused[0].fusion_sources) == {"external_event", "brain_inbox"}
    assert any(not c.fusion_sources for c in cands)  # plain candidates untagged


def test_no_fusion_for_single_source_or_unrelated_topics():
    a = _sig("hn", "external_event", "kubernetes operator autoscaling", "ops toil", "infra")
    b = _sig("manual", "brain_inbox", "watercolor painting composition tutor", "artists struggle", "art")
    issued = []

    def responder(req):
        issued.append(req.id)
        return LLMResponse(id=req.id, data={"candidates": []})

    cfg = {"user_template": "{title}", "fusion": {"user_template": "{theme}{bundle}"}}
    generate_llm([a, b], MockBackend(responder), cfg)
    assert not any(i.startswith("fusion-") for i in issued)


def test_fusion_pure_persona_stays_synthetic():
    p1 = _sig("persona", "pain_persona", "模拟痛点甲 共享主题 abc", "痛", "x")
    p2 = _sig("persona", "pain_persona", "模拟痛点乙 共享主题 abc", "痛", "x")
    data = {"candidates": [{"title": "T", "pain": "p", "solution": "s",
                            "mechanism": "m", "why_now": "w", "mvp_week1": "v", "target_user": "u"}]}
    out = _fusion_candidates_from_response([p1, p2], data)
    assert out[0].confidence == "synthetic"      # no real source → stays suspect
    assert out[0].fusion_sources == ["pain_persona"]


# --- ③ diversity Top-N (投资人复评 #3) -------------------------------------


def _scored(cid, title, alpha):
    return ScoredCandidate(
        candidate=_candidate(id=cid, title=title, solution=title),
        factors={}, alpha=alpha, decay=1.0,
    )


def test_select_diverse_top_n_drops_near_dupes_from_head():
    """Four near-identical 'voice memo to task' ideas must not fill the Top-N."""
    ranked = [
        _scored("a", "voice memo to task agent", 0.90),
        _scored("b", "voice memo to task tool", 0.89),       # near-dup of a
        _scored("c", "voice memo to task assistant", 0.88),  # near-dup of a
        _scored("d", "stripe invoice reconciliation", 0.70),
        _scored("e", "competitor changelog watcher", 0.60),
    ]
    picked = select_diverse_top_n(ranked, n=3, threshold=0.6)
    titles = [s.candidate.title for s in picked]
    # the head 'voice memo' cluster contributes only once; the other slots diversify
    assert titles[0] == "voice memo to task agent"
    assert "stripe invoice reconciliation" in titles
    assert "competitor changelog watcher" in titles
    # no two picked items are near-duplicates
    assert len(picked) == 3


def test_select_diverse_top_n_backfills_to_n_when_pool_thin():
    """If everything is similar, still return n items (length preserved)."""
    ranked = [
        _scored("a", "voice memo to task agent", 0.90),
        _scored("b", "voice memo to task tool", 0.89),
        _scored("c", "voice memo to task assistant", 0.88),
    ]
    picked = select_diverse_top_n(ranked, n=3, threshold=0.6)
    assert len(picked) == 3  # backfilled from parked near-dupes


def test_select_diverse_top_n_zero():
    assert select_diverse_top_n([_scored("a", "x", 0.5)], n=0) == []
