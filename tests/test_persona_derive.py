from idea_gen.persona import load_taxonomy
from idea_gen.persona.derive import derive_segments, save_derived, update_derived


def test_derive_recurring_target_users():
    items = [
        {"target_user": "跨境电商卖家", "category": "跨境"},
        {"target_user": "跨境电商卖家", "category": "选品"},
        {"target_user": "一次性人群", "category": "x"},   # only once -> not derived
    ]
    new = derive_segments(items, known_labels=set(), min_count=2)
    labels = {s.label for s in new}
    assert "跨境电商卖家" in labels
    assert "一次性人群" not in labels
    seg = next(s for s in new if s.label == "跨境电商卖家")
    assert seg.parent == "derived" and seg.is_leaf
    assert set(seg.evidence_topics) == {"跨境", "选品"}


def test_derive_skips_known_labels():
    base = load_taxonomy()
    known = {s.label for s in base}
    items = [{"target_user": list(known)[0]}] * 3   # already in taxonomy
    assert derive_segments(items, known, min_count=2) == []


def test_update_derived_persists_and_merges(tmp_path):
    path = tmp_path / "derived.jsonl.json"
    items = [{"target_user": "短视频代运营"}, {"target_user": "短视频代运营"}]
    base = load_taxonomy()
    merged = update_derived(items, base, path)
    assert any(s.label == "短视频代运营" for s in merged)
    # merged taxonomy includes derived
    full = load_taxonomy(derived_path=path)
    assert any(s.label == "短视频代运营" for s in full)
    # re-running with same labels doesn't duplicate
    again = update_derived(items, base, path)
    assert sum(1 for s in again if s.label == "短视频代运营") == 1
