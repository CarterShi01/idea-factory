"""Persistence helpers for idea rank overrides.

User-set rank overrides are stored in ``data/ranks.json`` as a flat
``{idea_id: rank}`` mapping. The HTTP layer and the CLI ``rank`` subcommand
both call :func:`set_override` so persistence logic lives in exactly one
place.
"""

from __future__ import annotations

import json
from pathlib import Path

from .generate import RANK_MAX, RANK_MIN

DEFAULT_RANKS_PATH = Path("data/ranks.json")


class InvalidRankError(ValueError):
    """Raised when a supplied rank is outside the allowed range."""


def _validate_rank(rank: int) -> int:
    if not isinstance(rank, int) or isinstance(rank, bool):
        raise InvalidRankError(f"rank must be an integer, got {type(rank).__name__}")
    if rank < RANK_MIN or rank > RANK_MAX:
        raise InvalidRankError(
            f"rank must be between {RANK_MIN} and {RANK_MAX} inclusive, got {rank}"
        )
    return rank


def get_overrides(path: Path = DEFAULT_RANKS_PATH) -> dict[str, int]:
    """Return the persisted rank-override mapping, or an empty dict if absent."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}


def set_override(idea_id: str, rank: int, path: Path = DEFAULT_RANKS_PATH) -> dict[str, int]:
    """Persist ``rank`` as the override for ``idea_id`` and return the full map."""
    _validate_rank(rank)
    if not idea_id:
        raise ValueError("idea_id must be a non-empty string")
    overrides = get_overrides(path)
    overrides[idea_id] = rank
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return overrides
