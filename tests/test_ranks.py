"""Tests for the rank-override persistence helper."""

from __future__ import annotations

import json

import pytest

from idea_factory.ranks import InvalidRankError, get_overrides, set_override


def test_set_override_writes_file(tmp_path):
    path = tmp_path / "ranks.json"
    set_override("abc123", 4, path=path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"abc123": 4}


def test_set_override_updates_existing(tmp_path):
    path = tmp_path / "ranks.json"
    set_override("abc123", 2, path=path)
    set_override("def456", 5, path=path)
    set_override("abc123", 3, path=path)
    assert get_overrides(path) == {"abc123": 3, "def456": 5}


def test_get_overrides_missing_file(tmp_path):
    assert get_overrides(tmp_path / "nope.json") == {}


@pytest.mark.parametrize("bad_rank", [0, 6, -1, 100])
def test_set_override_rejects_out_of_range(tmp_path, bad_rank):
    path = tmp_path / "ranks.json"
    with pytest.raises(InvalidRankError):
        set_override("abc", bad_rank, path=path)
    assert not path.exists()


def test_set_override_rejects_empty_id(tmp_path):
    path = tmp_path / "ranks.json"
    with pytest.raises(ValueError):
        set_override("", 3, path=path)
