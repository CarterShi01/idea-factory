"""HTTP API and programmatic accessors for generated idea candidates.

The HTTP layer is intentionally tiny: it loads mock ideas via the existing
pipeline modules and exposes them through ``GET /ideas``. Sort behaviour is
controlled by the ``sort`` query parameter (currently ``rank`` is the only
supported value, returning ideas ordered by ``rank`` descending).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

from .generate import generate_ideas
from .normalize import normalize_products
from .ranks import load_overrides

DEFAULT_PRODUCTS_PATH = Path("data/raw/sample_products.json")

_SUPPORTED_SORTS = {"rank"}


def _load_mock_ideas(products_path: Path = DEFAULT_PRODUCTS_PATH) -> list[dict[str, Any]]:
    raw = json.loads(products_path.read_text(encoding="utf-8"))
    return generate_ideas(normalize_products(raw))


def _apply_overrides(
    ideas: list[dict[str, Any]], overrides: dict[str, int]
) -> list[dict[str, Any]]:
    if not overrides:
        return list(ideas)
    merged: list[dict[str, Any]] = []
    for idea in ideas:
        idea_id = idea.get("id")
        if idea_id is not None and idea_id in overrides:
            updated = dict(idea)
            updated["rank"] = overrides[idea_id]
            merged.append(updated)
        else:
            merged.append(idea)
    return merged


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
    before sorting: any idea whose ``id`` matches a key in ``overrides`` (or
    in the persisted ``data/ranks.json`` when ``overrides`` is omitted) has
    its ``rank`` replaced with the override value.
    """
    if ideas is None:
        ideas = _load_mock_ideas()
    if overrides is None:
        overrides = load_overrides()
    ideas = _apply_overrides(ideas, overrides)
    if sort is None:
        return ideas
    if sort not in _SUPPORTED_SORTS:
        raise ValueError(f"Unsupported sort key: {sort!r}")
    if sort == "rank":
        return sorted(ideas, key=lambda idea: idea.get("rank", 0), reverse=True)
    return ideas


def create_app(products_path: Path = DEFAULT_PRODUCTS_PATH) -> Flask:
    app = Flask(__name__)

    @app.get("/ideas")
    def get_ideas():
        sort = request.args.get("sort")
        try:
            result = list_ideas(sort=sort, ideas=_load_mock_ideas(products_path))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    return app


app = create_app()
