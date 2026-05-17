"""Tests for rank override persistence and merge into list_ideas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from idea_factory import ranks
from idea_factory.api import list_ideas


def test_load_overrides_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ranks.load_overrides() == {}


def test_set_override_creates_file_on_first_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not Path("data/ranks.json").exists()
    ranks.set_override("abc12345", 4)
    path = Path("data/ranks.json")
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"abc12345": 4}


def test_overrides_persist_across_reloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ranks.set_override("abc12345", 4)
    ranks.set_override("def67890", 2)
    # A fresh call to load_overrides() simulates reading from a new process.
    assert ranks.load_overrides() == {"abc12345": 4, "def67890": 2}


def test_set_override_updates_existing_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ranks.set_override("abc12345", 2)
    ranks.set_override("abc12345", 5)
    assert ranks.load_overrides() == {"abc12345": 5}


@pytest.mark.parametrize("bad_rank", [0, -1, 6, 100])
def test_set_override_rejects_out_of_range_ranks(tmp_path, monkeypatch, bad_rank):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        ranks.set_override("abc12345", bad_rank)
    assert not Path("data/ranks.json").exists()


def test_list_ideas_merges_overrides_then_sorts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ideas = [
        {"id": "a", "rank": 2},
        {"id": "b", "rank": 5},
        {"id": "c", "rank": 1},
        {"id": "d", "rank": 4},
    ]
    ranks.set_override("c", 5)
    ranks.set_override("b", 1)
    sorted_ideas = list_ideas(sort="rank", ideas=ideas)
    assert [i["id"] for i in sorted_ideas] == ["c", "d", "a", "b"]
    assert {i["id"]: i["rank"] for i in sorted_ideas} == {
        "a": 2,
        "b": 1,
        "c": 5,
        "d": 4,
    }


def test_list_ideas_leaves_input_unchanged_when_overrides_apply(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ideas = [{"id": "a", "rank": 2}, {"id": "b", "rank": 5}]
    ranks.set_override("a", 5)
    list_ideas(sort="rank", ideas=ideas)
    # Original input dicts should not be mutated.
    assert ideas == [{"id": "a", "rank": 2}, {"id": "b", "rank": 5}]


def test_list_ideas_ignores_overrides_for_unknown_ids(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ideas = [{"id": "a", "rank": 2}, {"id": "b", "rank": 5}]
    ranks.set_override("zzz99999", 3)
    sorted_ideas = list_ideas(sort="rank", ideas=ideas)
    assert [i["id"] for i in sorted_ideas] == ["b", "a"]
