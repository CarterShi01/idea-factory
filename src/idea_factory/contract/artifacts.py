"""Stage-boundary artifacts: one JSON file per stage output, uniform envelope.

The old design had a single cross-half file (``ideas.json``); the from-zero
redesign makes EVERY stage boundary a disk artifact so any stage can be rerun
alone (``idea run --only diligence``), a run can resume mid-funnel, and each
stage's I/O contract is explicit and inspectable.

Envelope (all artifacts)::

    {"schema_version": 2, "stage": "...", "run_id": "...", "week": "...",
     "date": "YYYY-MM-DD", "count": N, "items": [...], ...extra}

``schema_version`` is checked on load -- the old "two halves refuse to run on
drifted schema" rule, generalized to every boundary. ``ideas.json`` (the rank
stage's output) keeps its historic name: it is still the cheap/expensive seam
that Studio and scripts read.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SCHEMA_VERSION = 2

# stage name -> artifact filename under output_dir (data/processed by default)
ARTIFACTS = {
    "recall": "recall.json",
    "triage": "triage.json",
    "generate": "candidates.json",
    "rank": "ideas.json",
    "enrich": "evidence.json",
    "diligence": "verdicts.json",
    "portfolio": "screened.json",
}


class ArtifactError(RuntimeError):
    """Missing/unreadable artifact or schema-version drift. Refuse to run."""


def artifact_path(output_dir: str | Path, stage: str) -> Path:
    return Path(output_dir) / ARTIFACTS[stage]


def save(
    output_dir: str | Path,
    stage: str,
    items: list[dict],
    *,
    run_id: str = "",
    week: str = "",
    today: date | str = "",
    extra: dict | None = None,
) -> Path:
    path = artifact_path(output_dir, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope: dict = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "run_id": run_id,
        "week": week,
        "date": today.isoformat() if isinstance(today, date) else str(today),
        "count": len(items),
        "items": items,
    }
    if extra:
        for k, v in extra.items():
            envelope.setdefault(k, v)
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(output_dir: str | Path, stage: str) -> dict:
    """Load a stage's output envelope; raise :class:`ArtifactError` on any drift."""
    path = artifact_path(output_dir, stage)
    if not path.exists():
        raise ArtifactError(
            f"missing artifact {path} -- run the '{stage}' stage first (idea run --to {stage})"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ArtifactError(f"unreadable artifact {path}: {exc}") from exc
    if not isinstance(data, dict) or "items" not in data:
        raise ArtifactError(
            f"{path} is not a stage artifact (legacy bare-list format?) -- re-run `idea run`"
        )
    got = data.get("schema_version")
    if got != SCHEMA_VERSION:
        raise ArtifactError(
            f"{path}: schema_version {got!r} != expected {SCHEMA_VERSION} -- "
            "stages drifted; re-run the producing stage"
        )
    return data


def load_items(output_dir: str | Path, stage: str) -> list[dict]:
    return load(output_dir, stage)["items"]
