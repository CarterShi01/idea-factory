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

RANKS_PATH = Path("data/ranks.json")


def load_overrides(path: Path = RANKS_PATH) -> dict[str, int]:
    """Return the persisted overrides mapping, or ``{}`` if absent."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items()}


def set_override(idea_id: str, rank: int, *, path: Path = RANKS_PATH) -> None:
    """Persist a rank override for ``idea_id``.

    Raises ``ValueError`` if ``rank`` is outside ``[RANK_MIN, RANK_MAX]``.
    """
    if not (RANK_MIN <= rank <= RANK_MAX):
        raise ValueError(
            f"rank must be in [{RANK_MIN}, {RANK_MAX}], got {rank!r}"
        )
    overrides = load_overrides(path)
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
