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
from .ranks import DEFAULT_RANKS_PATH, get_overrides

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


def list_ideas(
    sort: str | None = None,
    *,
    ideas: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return idea candidates, optionally sorted.

    ``sort="rank"`` returns ideas ordered by ``rank`` descending. ``ideas`` can
    be supplied to sort an arbitrary list; otherwise the mock ideas generated
    from the default sample products are used.
    """
    if ideas is None:
        ideas = _load_mock_ideas()
    if sort is None:
        return list(ideas)
    if sort not in _SUPPORTED_SORTS:
        raise ValueError(f"Unsupported sort key: {sort!r}")
    if sort == "rank":
        return sorted(ideas, key=lambda idea: idea.get("rank", 0), reverse=True)
    return list(ideas)


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
