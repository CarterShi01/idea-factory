"""Tests for idea generation, including the deterministic ``id`` field."""

from __future__ import annotations

import re

from idea_factory.generate import generate_ideas, generate_ideas_for_product

HEX8 = re.compile(r"^[0-9a-f]{8}$")


def _product(pid: str = "p1") -> dict:
    return {
        "id": pid,
        "name": "Acme",
        "categories": ["devtools"],
        "target_users": ["developers"],
        "pain_points": ["slow builds"],
    }


def test_idea_id_is_8_char_lowercase_hex():
    ideas = generate_ideas_for_product(_product())
    assert ideas, "expected at least one idea"
    for idea in ideas:
        assert "id" in idea
        assert isinstance(idea["id"], str)
        assert HEX8.match(idea["id"]), f"id {idea['id']!r} is not 8-char lowercase hex"


def test_idea_id_is_deterministic_across_calls():
    first = generate_ideas_for_product(_product())
    second = generate_ideas_for_product(_product())
    assert [i["id"] for i in first] == [i["id"] for i in second]


def test_idea_id_differs_per_pitch_index():
    ideas = generate_ideas_for_product(_product())
    ids = [i["id"] for i in ideas]
    assert len(ids) == len(set(ids)), f"expected unique ids per pitch index, got {ids}"


def test_idea_id_differs_per_source_product():
    a = generate_ideas_for_product(_product("alpha"))
    b = generate_ideas_for_product(_product("beta"))
    # For each pitch index, the id should differ when the source product id differs.
    for idea_a, idea_b in zip(a, b):
        assert idea_a["id"] != idea_b["id"]


def test_generate_ideas_preserves_id_field():
    ideas = generate_ideas([_product("alpha"), _product("beta")])
    for idea in ideas:
        assert HEX8.match(idea["id"])


def test_inspiration_source_defaults_to_sample():
    ideas = generate_ideas_for_product(_product())
    assert all(idea["inspiration_source"] == "sample" for idea in ideas)


def test_inspiration_source_threaded_from_product_source():
    product = {**_product(), "source": "hackernews"}
    ideas = generate_ideas_for_product(product)
    assert all(idea["inspiration_source"] == "hackernews" for idea in ideas)
