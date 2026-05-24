"""Tests for the ``python -m idea_factory hello`` CLI subcommand."""

from __future__ import annotations

from idea_factory import cli


def test_hello_prints_expected_string(capsys):
    exit_code = cli.hello()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Hello from idea-factory!\n"
    assert captured.err == ""


def test_hello_via_main(capsys):
    exit_code = cli.main(["hello"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Hello from idea-factory!\n"
    assert captured.err == ""
