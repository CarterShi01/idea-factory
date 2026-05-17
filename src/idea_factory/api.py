"""HTTP API and programmatic accessors for generated idea candidates.

The HTTP layer is intentionally tiny: it loads mock ideas via the existing
pipeline modules and exposes them through ``GET /ideas``. Sort behaviour is
controlled by the ``sort`` query parameter (currently ``rank`` is the only
supported value, returning ideas ordered by ``rank`` descending).

Rank overrides supplied through ``PATCH /ideas/<idea-id>/rank`` are persisted
via :mod:`idea_factory.ranks` and applied transparently on every read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from .generate import RANK_MAX, RANK_MIN, generate_ideas
from .normalize import normalize_products
from .ranks import DEFAULT_RANKS_PATH, get_overrides, set_override

DEFAULT_PRODUCTS_PATH = Path("data/raw/sample_products.json")

_SUPPORTED_SORTS = {"rank"}


def _load_mock_ideas(
    products_path: Path = DEFAULT_PRODUCTS_PATH,
    ranks_path: Path = DEFAULT_RANKS_PATH,
) -> list[dict[str, Any]]:
    raw = json.loads(products_path.read_text(encoding="utf-8"))
    ideas = generate_ideas(normalize_products(raw))
    overrides = get_overrides(ranks_path)
    if overrides:
        for idea in ideas:
            override = overrides.get(idea.get("id"))
            if override is not None:
                idea["rank"] = override
    return ideas


def _apply_overrides(
    ideas: list[dict[str, Any]],
    overrides: dict[str, int],
) -> list[dict[str, Any]]:
    if not overrides:
        return ideas
    updated: list[dict[str, Any]] = []
    for idea in ideas:
        idea_id = idea.get("id")
        if isinstance(idea_id, str) and idea_id in overrides:
            idea = {**idea, "rank": overrides[idea_id]}
        updated.append(idea)
    return updated


def list_ideas(
    sort: str | None = None,
    *,
    ideas: list[dict[str, Any]] | None = None,
    overrides: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Return idea candidates, optionally sorted.

    ``sort="rank"`` returns ideas ordered by ``rank`` descending. ``ideas`` can
    be supplied to sort an arbitrary list; otherwise the mock ideas generated
    from the default sample products are used. Rank overrides are merged in
    before sorting when ``overrides`` is provided; pass an explicit empty dict
    to suppress override loading.
    """
    if ideas is None:
        ideas = _load_mock_ideas()
    if overrides is not None:
        ideas = _apply_overrides(ideas, overrides)
    if sort is None:
        return ideas
    if sort not in _SUPPORTED_SORTS:
        raise ValueError(f"Unsupported sort key: {sort!r}")
    if sort == "rank":
        return sorted(ideas, key=lambda idea: idea.get("rank", 0), reverse=True)
    return ideas


def create_app(
    products_path: Path = DEFAULT_PRODUCTS_PATH,
    overrides_path: Path = DEFAULT_RANKS_PATH,
) -> Flask:
    app = Flask(__name__)

    def _current_ideas() -> list[dict[str, Any]]:
        return _load_mock_ideas(products_path, overrides_path)

    @app.get("/ideas")
    def get_ideas():
        sort = request.args.get("sort")
        try:
            result = list_ideas(sort=sort, ideas=_current_ideas())
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @app.patch("/ideas/<idea_id>/rank")
    def patch_idea_rank(idea_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "rank" not in payload:
            return (
                jsonify({"error": "Request body must be JSON with a 'rank' field."}),
                400,
            )
        rank = payload["rank"]
        if isinstance(rank, bool) or not isinstance(rank, int):
            return jsonify({"error": "'rank' must be an integer."}), 400
        if rank < RANK_MIN or rank > RANK_MAX:
            return (
                jsonify(
                    {"error": f"'rank' must be between {RANK_MIN} and {RANK_MAX}."}
                ),
                400,
            )

        ideas = _current_ideas()
        match = next((idea for idea in ideas if idea.get("id") == idea_id), None)
        if match is None:
            return jsonify({"error": f"No idea found with id {idea_id!r}."}), 404

        set_override(idea_id, rank, path=overrides_path)
        updated = {**match, "rank": rank}
        return jsonify(updated), 200

    return app


app = create_app()
