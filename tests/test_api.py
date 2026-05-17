"""Tests for the ideas API: list, sort, id format, and PATCH rank override behaviour."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from idea_factory.api import create_app, list_ideas
from idea_factory.generate import RANK_MAX, RANK_MIN

HEX8 = re.compile(r"^[0-9a-f]{8}$")


@pytest.fixture
def overrides_path(tmp_path: Path) -> Path:
    return tmp_path / "overrides.json"


@pytest.fixture
def client(overrides_path: Path):
    app = create_app(overrides_path=overrides_path)
    return app.test_client()


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


def test_get_ideas_endpoint_sorted_by_rank(client):
    response = client.get("/ideas?sort=rank")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    ranks = [item["rank"] for item in payload]
    assert ranks == sorted(ranks, reverse=True)
    assert all(RANK_MIN <= r <= RANK_MAX for r in ranks)


def test_get_ideas_endpoint_rejects_unknown_sort(client):
    response = client.get("/ideas?sort=bogus")
    assert response.status_code == 400


def test_get_ideas_endpoint_includes_id_field(client):
    response = client.get("/ideas")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    for item in payload:
        assert "id" in item
        assert HEX8.match(item["id"])


def test_get_ideas_endpoint_sorted_by_rank_includes_id_field(client):
    response = client.get("/ideas?sort=rank")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    for item in payload:
        assert "id" in item
        assert HEX8.match(item["id"])


def _first_idea(client) -> dict:
    response = client.get("/ideas")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload, "expected non-empty ideas list"
    return payload[0]


def test_patch_rank_updates_idea_and_reflects_in_get(client, overrides_path):
    target = _first_idea(client)
    idea_id = target["id"]
    new_rank = RANK_MIN if target["rank"] == RANK_MAX else RANK_MAX

    response = client.patch(
        f"/ideas/{idea_id}/rank",
        data=json.dumps({"rank": new_rank}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == idea_id
    assert body["rank"] == new_rank

    listing = client.get("/ideas").get_json()
    match = next(item for item in listing if item["id"] == idea_id)
    assert match["rank"] == new_rank

    sorted_listing = client.get("/ideas?sort=rank").get_json()
    ranks = [item["rank"] for item in sorted_listing]
    assert ranks == sorted(ranks, reverse=True)
    match_sorted = next(item for item in sorted_listing if item["id"] == idea_id)
    assert match_sorted["rank"] == new_rank

    persisted = json.loads(overrides_path.read_text(encoding="utf-8"))
    assert persisted == {idea_id: new_rank}


@pytest.mark.parametrize("bad_rank", [0, 6, -1, 100])
def test_patch_rank_out_of_range_returns_400(client, bad_rank):
    target = _first_idea(client)
    response = client.patch(
        f"/ideas/{target['id']}/rank",
        data=json.dumps({"rank": bad_rank}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize("bad_rank", ["3", 2.5, None, True])
def test_patch_rank_non_integer_returns_400(client, bad_rank):
    target = _first_idea(client)
    response = client.patch(
        f"/ideas/{target['id']}/rank",
        data=json.dumps({"rank": bad_rank}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_patch_rank_unknown_idea_returns_404(client):
    response = client.patch(
        "/ideas/does-not-exist/rank",
        data=json.dumps({"rank": 3}),
        content_type="application/json",
    )
    assert response.status_code == 404
    assert "error" in response.get_json()


def test_patch_rank_missing_field_returns_400(client):
    target = _first_idea(client)
    response = client.patch(
        f"/ideas/{target['id']}/rank",
        data=json.dumps({"not_rank": 3}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_patch_rank_malformed_json_returns_400(client):
    target = _first_idea(client)
    response = client.patch(
        f"/ideas/{target['id']}/rank",
        data="{not json",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert "error" in response.get_json()
