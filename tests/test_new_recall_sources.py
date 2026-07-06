"""Tests for the pipeline-v2 "money trace" recall channels: jobs / marketplace / reviews."""

from __future__ import annotations

from pathlib import Path

from idea_factory.contract.models import SOURCE_EXTERNAL
from idea_factory.stages.recall.channels import CollectContext, REGISTRY, ensure_loaded

REPO_DATA_DIR = Path("data")


def test_new_adapters_are_registered():
    ensure_loaded()
    assert {"jobs", "marketplace", "reviews"} <= set(REGISTRY.keys())
    for name in ("jobs", "marketplace", "reviews"):
        adapter = REGISTRY[name]
        assert adapter.source == SOURCE_EXTERNAL
        assert adapter.needs_llm is False


def test_offline_reads_fixture_and_never_touches_network():
    ensure_loaded()
    ctx = CollectContext(raw_dir=REPO_DATA_DIR / "raw", cache_dir=REPO_DATA_DIR / "cache", live=False)
    for name in ("jobs", "marketplace", "reviews"):
        records = REGISTRY[name].collect(ctx)
        assert len(records) >= 2
        for r in records:
            assert r["source"] == SOURCE_EXTERNAL
            assert r.get("pain")
            assert r.get("url", "").startswith("https://")


def test_live_mode_is_a_stubbed_noop():
    ensure_loaded()
    ctx = CollectContext(raw_dir=REPO_DATA_DIR / "raw", cache_dir=REPO_DATA_DIR / "cache", live=True)
    for name in ("jobs", "marketplace", "reviews"):
        assert REGISTRY[name].collect(ctx) == []


def test_missing_fixture_returns_empty(tmp_path):
    ensure_loaded()
    ctx = CollectContext(raw_dir=tmp_path / "raw", cache_dir=tmp_path / "cache", live=False)
    for name in ("jobs", "marketplace", "reviews"):
        assert REGISTRY[name].collect(ctx) == []
