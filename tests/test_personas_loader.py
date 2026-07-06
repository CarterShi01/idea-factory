"""Tests for idea_core.personas — the shared read-only persona-pool loader."""

from __future__ import annotations

import json

from idea_factory.runtime.personas import load_persona_pool


def test_loads_repo_personas_json():
    pool = load_persona_pool()  # default path: data/raw/personas.json
    assert isinstance(pool, list)
    assert len(pool) > 0
    assert all("persona" in p for p in pool)


def test_missing_file_returns_empty(tmp_path):
    assert load_persona_pool(tmp_path / "nope.json") == []


def test_malformed_json_returns_empty(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json", encoding="utf-8")
    assert load_persona_pool(p) == []


def test_non_list_json_returns_empty(tmp_path):
    p = tmp_path / "obj.json"
    p.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_persona_pool(p) == []
