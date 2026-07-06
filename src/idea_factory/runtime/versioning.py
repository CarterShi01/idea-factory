"""Run versioning for the processed pipeline outputs (stdlib only, fault-tolerant).

Every evaluation run can be *committed* as an immutable **version** so the WebUI
(studio) can browse past runs instead of only the latest overwrite.

Directory layout under ``data/processed/``::

    versions/
      index.json                 # newest-first: [{"id","created_at","ui_count","en","zh"}]
      <version_id>/              # version_id = "YYYY-MM-DD_N" (N = Nth run that day, 1-based)
        ideas.json  screened.json  ideas.md  decision_memos.md

Design notes:
* This module lives in ``idea_core`` on purpose — both halves (idea_gen /
  idea_eval) and the studio backend may import it, and neither half imports the
  other (isolation rule). It only depends on ``idea_core.models``.
* ``today_iso`` is always passed in by the caller (tests need a controllable
  date); :func:`today_iso` is a convenience default, never called implicitly.
* Every reader tolerates a missing / malformed tree and degrades to empty.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path

from idea_factory.contract.models import bucket_of

# The four flat artifacts a run produces; only the ones that exist get copied.
_ARTIFACTS = ("ideas.json", "screened.json", "ideas.md", "decision_memos.md")
_VALID_NAMES = frozenset(_ARTIFACTS)
_INDEX_NAME = "index.json"
_VERSIONS_DIR = "versions"

# verdicts that survive the kill-gate; "kill" is excluded from the UI list
_SURVIVING = ("pursue", "review")
_UI_CAP = 20  # the WebUI/top-of-funnel shows at most this many survivors


def today_iso() -> str:
    """Convenience default for the reference date (``YYYY-MM-DD``).

    Never called implicitly by the helpers below — callers pass ``today_iso``
    explicitly so tests stay deterministic.
    """
    return date.today().isoformat()


def _versions_dir(processed_dir: str | Path) -> Path:
    return Path(processed_dir) / _VERSIONS_DIR


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def next_version_id(processed_dir: str | Path, today_iso: str) -> str:
    """Next version id for ``today_iso`` — ``f"{today_iso}_{N+1}"``.

    Scans existing ``versions/<today_iso>_*`` directories and picks one past the
    current max suffix (1-based). Tolerates a missing tree / junk names.
    """
    vdir = _versions_dir(processed_dir)
    prefix = f"{today_iso}_"
    max_n = 0
    if vdir.is_dir():
        for entry in vdir.iterdir():
            if not entry.is_dir() or not entry.name.startswith(prefix):
                continue
            suffix = entry.name[len(prefix):]
            try:
                max_n = max(max_n, int(suffix))
            except ValueError:
                continue
    return f"{today_iso}_{max_n + 1}"


def _stats(dest: Path) -> dict:
    """Count survivors (ui_count, capped) and their en/zh source split.

    Joins ``screened.json`` (which carries ``idea_id`` + ``verdict``) with
    ``ideas.json`` (which carries each idea's ``source``) to bucket survivors
    via :func:`idea_core.models.bucket_of`. ``en + zh == ui_count``.
    """
    screened = _read_json(dest / "screened.json", [])
    ideas = _read_json(dest / "ideas.json", [])
    source_of = {i.get("id", ""): i.get("source", "") for i in ideas if isinstance(i, dict)}
    survivors = [e for e in screened if isinstance(e, dict) and e.get("verdict") in _SURVIVING]
    survivors = survivors[:_UI_CAP]
    en = zh = 0
    for e in survivors:
        if bucket_of(source_of.get(e.get("idea_id", ""), "")) == "en":
            en += 1
        else:
            zh += 1
    return {"ui_count": len(survivors), "en": en, "zh": zh}


def commit_version(processed_dir: str | Path, today_iso: str) -> str:
    """Snapshot the flat outputs into ``versions/<new_id>/`` and index it.

    Copies whichever of the four flat artifacts currently exist under
    ``processed_dir``, computes en/zh/ui_count from the copied snapshot, prepends
    the entry to ``index.json`` (newest-first) and returns the new ``version_id``.
    """
    processed_dir = Path(processed_dir)
    vdir = _versions_dir(processed_dir)
    new_id = next_version_id(processed_dir, today_iso)
    dest = vdir / new_id
    dest.mkdir(parents=True, exist_ok=True)

    for name in _ARTIFACTS:
        src = processed_dir / name
        if src.is_file():
            shutil.copy2(src, dest / name)

    entry = {"id": new_id, "created_at": datetime.now().isoformat(timespec="seconds")}
    entry.update(_stats(dest))

    index = list_versions(processed_dir)
    index.insert(0, entry)
    (vdir / _INDEX_NAME).write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return new_id


def list_versions(processed_dir: str | Path) -> list[dict]:
    """All versions, newest-first (from ``index.json``); ``[]`` if none."""
    index = _read_json(_versions_dir(processed_dir) / _INDEX_NAME, [])
    return index if isinstance(index, list) else []


def latest_version(processed_dir: str | Path) -> str | None:
    """Id of the newest version, or ``None`` if there are no versions."""
    versions = list_versions(processed_dir)
    if not versions:
        return None
    first = versions[0]
    return first.get("id") if isinstance(first, dict) else None


def read_version(processed_dir: str | Path, version_id: str, name: str):
    """Read one artifact (``name`` in :data:`_VALID_NAMES`) of a version.

    Returns parsed JSON for ``*.json``, text for ``*.md``; ``None`` if the
    version, file or name is missing/invalid.
    """
    if name not in _VALID_NAMES:
        return None
    path = _versions_dir(processed_dir) / version_id / name
    if not path.is_file():
        return None
    if name.endswith(".json"):
        return _read_json(path, None)
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
