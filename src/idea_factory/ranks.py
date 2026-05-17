"""Persistent storage for user-set rank overrides.

Overrides are stored in ``data/ranks.json`` as a flat JSON object mapping
idea ids (``str``) to ranks (``int`` in ``[RANK_MIN, RANK_MAX]``). Writes are
atomic: the new contents are written to a temp file in the same directory
and then renamed over the target path so partial writes are not observable.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .generate import RANK_MAX, RANK_MIN

DEFAULT_RANKS_PATH = Path("data/ranks.json")
RANKS_PATH = DEFAULT_RANKS_PATH  # backward-compat alias


class InvalidRankError(ValueError):
    """Raised when a supplied rank is outside the allowed range."""


def get_overrides(path: Path = DEFAULT_RANKS_PATH) -> dict[str, int]:
    """Return the persisted overrides mapping, or ``{}`` if absent."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool)}


# backward-compat alias used by api.py pre-T04
load_overrides = get_overrides


def set_override(idea_id: str, rank: int, path: Path = DEFAULT_RANKS_PATH) -> dict[str, int]:
    """Persist a rank override for ``idea_id`` and return the full map.

    Raises ``InvalidRankError`` if ``rank`` is outside ``[RANK_MIN, RANK_MAX]``.
    Raises ``ValueError`` if ``idea_id`` is empty.
    """
    if not isinstance(rank, int) or isinstance(rank, bool):
        raise InvalidRankError(f"rank must be an integer, got {type(rank).__name__}")
    if not (RANK_MIN <= rank <= RANK_MAX):
        raise InvalidRankError(
            f"rank must be between {RANK_MIN} and {RANK_MAX} inclusive, got {rank}"
        )
    if not idea_id:
        raise ValueError("idea_id must be a non-empty string")
    overrides = get_overrides(path)
    overrides[str(idea_id)] = int(rank)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".ranks-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(overrides, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return overrides
