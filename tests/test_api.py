"""Tests for the ideas API sort behaviour."""

from __future__ import annotations

import re

from idea_factory.api import create_app, list_ideas
from idea_factory.generate import RANK_MAX, RANK_MIN

HEX8 = re.compile(r"^[0-9a-f]{8}$")


def test_list_ideas_sort_rank_descending():
    ideas = [
        {"id": "a", "rank": 2},
        {"id": "b", "rank": 5},
        {"id": "c", "rank": 1},
        {"id": "d", "rank": 4},
    ]
    sorted_ideas = list_ideas(sort="rank", ideas=ideas)
    assert [i["id"] for i in sorted_ideas] == ["b", "d", "a", "c"]


def test_list_ideas_no_sort_preserves_order():
    ideas = [{"id": "a", "rank": 1}, {"id": "b", "rank": 5}]
    assert list_ideas(ideas=ideas) == ideas


def test_get_ideas_endpoint_sorted_by_rank():
    app = create_app()
    client = app.test_client()
    response = client.get("/ideas?sort=rank")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    ranks = [item["rank"] for item in payload]
    assert ranks == sorted(ranks, reverse=True)
    assert all(RANK_MIN <= r <= RANK_MAX for r in ranks)


def test_get_ideas_endpoint_rejects_unknown_sort():
    app = create_app()
    client = app.test_client()
    response = client.get("/ideas?sort=bogus")
    assert response.status_code == 400


def test_get_ideas_endpoint_includes_id_field():
    app = create_app()
    client = app.test_client()
    response = client.get("/ideas")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    for item in payload:
        assert "id" in item
        assert HEX8.match(item["id"])


def test_get_ideas_endpoint_sorted_by_rank_includes_id_field():
    app = create_app()
    client = app.test_client()
    response = client.get("/ideas?sort=rank")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    for item in payload:
        assert "id" in item
        assert HEX8.match(item["id"])
