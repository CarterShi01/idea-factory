from idea_factory.stages.triage.dedup import dedupe_signals
from idea_factory.runtime.textsim import jaccard
from idea_factory.stages.recall.normalize import normalize_record


def _sig(title, pain):
    return normalize_record({"source_name": "test", "title": title, "pain": pain})


def test_jaccard_basics():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert jaccard(set(), {"a"}) == 0.0


def test_exact_duplicate_dropped():
    a = _sig("Same idea", "founders waste hours on manual work")
    b = _sig("Same idea", "founders waste hours on manual work")
    kept, dropped = dedupe_signals([a, b])
    assert len(kept) == 1
    assert len(dropped) == 1


def test_near_duplicate_dropped():
    a = _sig("A", "founders waste hours reconciling stripe payouts manually")
    b = _sig("B", "founders waste hours reconciling stripe payouts by hand manually")
    kept, _ = dedupe_signals([a, b], threshold=0.6)
    assert len(kept) == 1


def test_distinct_signals_kept():
    a = _sig("A", "developers lack a privacy preserving local agent")
    b = _sig("B", "investors are overwhelmed by inbound deal flow")
    kept, dropped = dedupe_signals([a, b])
    assert len(kept) == 2
    assert dropped == []


def test_seen_keys_filter_across_runs():
    a = _sig("A", "developers lack a local agent")
    seen = {a.dedup_key}
    kept, dropped = dedupe_signals([a], seen_keys=seen)
    assert kept == []
    assert len(dropped) == 1
