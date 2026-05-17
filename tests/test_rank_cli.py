"""Tests for the ``python -m idea_factory rank`` CLI subcommand."""

from __future__ import annotations

import json

import pytest

from idea_factory.api import _load_mock_ideas, list_ideas
from idea_factory.cli import main


@pytest.fixture
def isolated_ranks_path(tmp_path, monkeypatch):
    """Redirect rank-override persistence to a temp file for each test."""
    ranks_path = tmp_path / "ranks.json"
    monkeypatch.setattr("idea_factory.cli.DEFAULT_RANKS_PATH", ranks_path)
    monkeypatch.setattr("idea_factory.ranks.DEFAULT_RANKS_PATH", ranks_path)
    return ranks_path


def _first_idea_id() -> str:
    ideas = _load_mock_ideas()
    assert ideas, "expected at least one generated idea"
    return ideas[0]["id"]


def test_rank_cli_persists_override(isolated_ranks_path, capsys):
    idea_id = _first_idea_id()

    exit_code = main(["rank", idea_id, "4"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert f"Updated {idea_id} to rank 4" in captured.out
    assert captured.err == ""

    stored = json.loads(isolated_ranks_path.read_text(encoding="utf-8"))
    assert stored == {idea_id: 4}

    refreshed = list_ideas(
        sort="rank",
        ideas=_load_mock_ideas(ranks_path=isolated_ranks_path),
    )
    match = next(idea for idea in refreshed if idea["id"] == idea_id)
    assert match["rank"] == 4


@pytest.mark.parametrize("bad_rank", ["0", "6", "99", "-1"])
def test_rank_cli_rejects_out_of_range(isolated_ranks_path, capsys, bad_rank):
    idea_id = _first_idea_id()

    exit_code = main(["rank", idea_id, bad_rank])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "rank must be" in captured.err
    assert not isolated_ranks_path.exists()


def test_rank_cli_rejects_unknown_idea(isolated_ranks_path, capsys):
    exit_code = main(["rank", "does-not-exist", "3"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unknown idea id" in captured.err
    assert not isolated_ranks_path.exists()


def test_rank_cli_non_integer_rank_is_argparse_error(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["rank", "anything", "not-an-int"])
    assert excinfo.value.code == 2
