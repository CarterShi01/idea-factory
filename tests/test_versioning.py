"""Tests for idea_core.versioning — run snapshotting + index."""

from __future__ import annotations

import json

from idea_core import versioning


def _write_flat(processed, ideas, screened, ideas_md="# ideas", memos="# memos"):
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "ideas.json").write_text(json.dumps(ideas), encoding="utf-8")
    (processed / "screened.json").write_text(json.dumps(screened), encoding="utf-8")
    (processed / "ideas.md").write_text(ideas_md, encoding="utf-8")
    (processed / "decision_memos.md").write_text(memos, encoding="utf-8")


def test_commit_twice_and_index(tmp_path):
    processed = tmp_path / "processed"
    ideas = [
        {"id": "a", "source": "external_event"},  # en
        {"id": "b", "source": "pain_persona"},    # zh
        {"id": "c", "source": "brain_inbox"},     # zh
    ]
    screened = [
        {"idea_id": "a", "verdict": "pursue"},
        {"idea_id": "b", "verdict": "review"},
        {"idea_id": "c", "verdict": "kill"},
    ]
    _write_flat(processed, ideas, screened)

    v1 = versioning.commit_version(processed, "2026-07-04")
    assert v1 == "2026-07-04_1"

    v2 = versioning.commit_version(processed, "2026-07-04")
    assert v2 == "2026-07-04_2"

    # a different day restarts the counter at 1
    v_next = versioning.next_version_id(processed, "2026-07-05")
    assert v_next == "2026-07-05_1"

    index = versioning.list_versions(processed)
    assert [e["id"] for e in index] == ["2026-07-04_2", "2026-07-04_1"]  # newest-first

    # stats: 2 survivors (a=en, b=zh), c killed -> excluded
    top = index[0]
    assert top["ui_count"] == 2
    assert top["en"] == 1
    assert top["zh"] == 1
    assert "created_at" in top

    assert versioning.latest_version(processed) == "2026-07-04_2"


def test_read_version_files(tmp_path):
    processed = tmp_path / "processed"
    ideas = [{"id": "a", "source": "external_event"}]
    screened = [{"idea_id": "a", "verdict": "pursue"}]
    _write_flat(processed, ideas, screened, ideas_md="# hello", memos="# memo body")

    vid = versioning.commit_version(processed, "2026-07-04")

    assert versioning.read_version(processed, vid, "ideas.json") == ideas
    assert versioning.read_version(processed, vid, "screened.json") == screened
    assert versioning.read_version(processed, vid, "ideas.md") == "# hello"
    assert versioning.read_version(processed, vid, "decision_memos.md") == "# memo body"
    # invalid name / missing version -> None
    assert versioning.read_version(processed, vid, "nope.json") is None
    assert versioning.read_version(processed, "2099-01-01_9", "ideas.json") is None


def test_empty_tree(tmp_path):
    processed = tmp_path / "processed"
    assert versioning.list_versions(processed) == []
    assert versioning.latest_version(processed) is None
    assert versioning.next_version_id(processed, "2026-07-04") == "2026-07-04_1"


def test_commit_copies_only_existing(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    # only screened.json exists (no ideas.json) — commit must not choke
    (processed / "screened.json").write_text(
        json.dumps([{"idea_id": "x", "verdict": "pursue"}]), encoding="utf-8"
    )
    vid = versioning.commit_version(processed, "2026-07-04")
    assert vid == "2026-07-04_1"
    # ideas.json absent -> source unknown -> bucketed zh
    idx = versioning.list_versions(processed)[0]
    assert idx["ui_count"] == 1 and idx["zh"] == 1 and idx["en"] == 0
    assert versioning.read_version(processed, vid, "ideas.json") is None
