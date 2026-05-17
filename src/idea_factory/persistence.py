"""Persistence helpers for user-supplied idea rank overrides.

Overrides are stored as a JSON object mapping ``idea_id`` to integer rank in a
single file. The helpers ``set_override`` and ``load_overrides`` are the only
public surface; callers should not read or write the override file directly.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_OVERRIDES_PATH = Path("data/overrides.json")


def load_overrides(path: Path = DEFAULT_OVERRIDES_PATH) -> dict[str, int]:
    """Return the persisted ``idea_id -> rank`` overrides, or an empty dict."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    overrides: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool):
            overrides[key] = value
    return overrides


def set_override(idea_id: str, rank: int, path: Path = DEFAULT_OVERRIDES_PATH) -> None:
    """Persist a rank override for ``idea_id``, creating the file if needed."""
    overrides = load_overrides(path)
    overrides[idea_id] = rank
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, sort_keys=True), encoding="utf-8")
