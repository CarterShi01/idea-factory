from idea_gen.persona import (
    Segment,
    flatten_leaves,
    load_taxonomy,
    persona_value,
    segment_priority,
    select_segments,
)


def test_load_and_flatten_leaves():
    segs = load_taxonomy()
    assert len(segs) >= 5
    leaves = flatten_leaves(segs)
    # leaves have no children; a parent with children (mongolian) is excluded
    assert all(s.is_leaf for s in leaves)
    ids = {s.id for s in leaves}
    assert "mongolian.elderly" in ids and "mongolian" not in ids


def test_select_returns_topn_sorted():
    segs = load_taxonomy()
    picked = select_segments(segs, history=None, n=3, today="2026-06-13")
    assert len(picked) == 3
    pr = [segment_priority(s, None, "2026-06-13") for s in picked]
    assert pr == sorted(pr, reverse=True)


def test_staleness_bonus_promotes_unmined():
    fresh = Segment(id="a", label="A", monetizability_prior=0.6, reachability=0.6, last_mined_on="2026-06-13")
    stale = Segment(id="b", label="B", monetizability_prior=0.6, reachability=0.6, last_mined_on="1970-01-01")
    today = "2026-06-13"
    assert segment_priority(stale, None, today) > segment_priority(fresh, None, today)


def test_persona_value_formula():
    assert persona_value(1.0, 1.0, 1.0, 0.0) == 0.85   # 0.35+0.30+0.20-0
    assert persona_value(0.0, 0.0, 0.0, 1.0) == -0.15
    # monetizability + severity dominate (per business logic)
    high = persona_value(0.9, 0.9, 0.5, 0.2)
    low = persona_value(0.2, 0.2, 0.5, 0.2)
    assert high > low
