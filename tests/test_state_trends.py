from idea_core.state import SeenStore, SignalHistory
from idea_core.trends import PEAKED, RISING, STEADY, classify


def test_seenstore_observe_and_dedup(tmp_path):
    s = SeenStore.load(tmp_path / "seen.jsonl")
    assert s.observe("k1", "2026-06-10") is True       # new
    assert s.observe("k1", "2026-06-11") is False      # seen again
    assert s.is_seen("k1") and not s.is_seen("k2")
    assert s.hit_count("k1") == 2
    s.save()
    reloaded = SeenStore.load(tmp_path / "seen.jsonl")
    assert reloaded.is_seen("k1")
    assert reloaded.hit_count("k1") == 2
    assert reloaded._by_key["k1"]["first_seen"] == "2026-06-10"
    assert reloaded._by_key["k1"]["last_seen"] == "2026-06-11"


def test_signalhistory_series_zero_filled(tmp_path):
    h = SignalHistory.load(tmp_path / "hist.jsonl")
    h.add("ai-agent", "2026-06-10", 2)
    h.add("ai-agent", "2026-06-12", 5)
    series = h.series("ai-agent", window=4, end="2026-06-12")
    assert series == [0, 2, 0, 5]  # 06-09,06-10,06-11,06-12
    h.save()
    assert SignalHistory.load(tmp_path / "hist.jsonl").series("ai-agent", 4, "2026-06-12") == [0, 2, 0, 5]


def test_trends_rising_steady_peaked():
    # a clear surge at the end -> rising
    rising = [1, 1, 2, 1, 2, 1, 1, 2, 1, 9]
    assert classify(rising)[0] == RISING
    assert classify(rising)[1] > 0
    # flat -> steady
    assert classify([3, 3, 3, 3, 3, 3, 3, 3, 3, 3])[0] == STEADY
    # short series -> steady, 0 (cold start)
    assert classify([1, 2, 3]) == (STEADY, 0.0)


def test_trends_peaked_on_drop():
    peaked = [9, 8, 9, 8, 9, 8, 9, 8, 9, 0]
    assert classify(peaked)[0] == PEAKED
