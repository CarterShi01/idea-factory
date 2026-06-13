"""Stage 1 -- collect raw records from the three idea sources.

This MVP is **offline by contract**: every loader reads from local files under
``data/raw/`` and makes no network calls. Live sources (Hacker News / arXiv /
GitHub Trending RSS, etc.) are stage 1 of the roadmap and belong behind an
explicit, opt-in ``collect`` command -- never on this default demo path.

Each loader returns a list of plain ``dict`` raw records tagged with their
``source``. The :mod:`idea_factory.normalize` stage turns these into
:class:`~idea_factory.models.Signal` objects.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import SOURCE_BRAIN, SOURCE_EXTERNAL, SOURCE_PERSONA


def _read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else [data]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def collect_external(raw_dir: Path) -> list[dict]:
    """External-world signals: product launches, trends, papers (offline sample)."""
    records = _read_json(raw_dir / "sample_signals.json")
    for r in records:
        r.setdefault("source", SOURCE_EXTERNAL)
    return records


def collect_brain(raw_dir: Path) -> list[dict]:
    """Founder's own ideas, one JSON object per line in ``inbox.jsonl``."""
    records = _read_jsonl(raw_dir / "inbox.jsonl")
    for r in records:
        r.setdefault("source", SOURCE_BRAIN)
        r.setdefault("source_name", "manual")
    return records


def collect_personas(raw_dir: Path) -> list[dict]:
    """Simulated pain analysis.

    Each persona declares a target user and a list of pains. We expand them into
    one synthetic signal per pain. These are flagged ``confidence=synthetic`` so
    downstream stages can treat them with the suspicion they deserve -- personas
    tend to be systematically optimistic.
    """
    personas = _read_json(raw_dir / "personas.json")
    records: list[dict] = []
    for persona in personas:
        who = persona.get("persona", "a target user")
        for pain in persona.get("pains", []):
            records.append(
                {
                    "source": SOURCE_PERSONA,
                    "source_name": "persona",
                    "title": pain.get("summary", ""),
                    "text": pain.get("verbatim", pain.get("summary", "")),
                    "pain": pain.get("summary", ""),
                    "category": persona.get("domain"),
                    "target_user": who,
                    "confidence": "synthetic",
                    # A synthetic pain only earns its place if at least one real
                    # signal corroborates it; we surface the flag here and leave
                    # the corroboration check to a later roadmap stage.
                    "corroborated": pain.get("corroborated", False),
                }
            )
    return records


def collect_all(data_dir: Path, sources: list[str] | None = None) -> list[dict]:
    """Collect from all (or a subset of) the three sources.

    ``sources`` filters by the ``SOURCE_*`` constants; ``None`` means all.
    """
    raw_dir = Path(data_dir) / "raw"
    loaders = {
        SOURCE_EXTERNAL: collect_external,
        SOURCE_BRAIN: collect_brain,
        SOURCE_PERSONA: collect_personas,
    }
    wanted = sources or list(loaders)
    records: list[dict] = []
    for source in wanted:
        loader = loaders.get(source)
        if loader:
            records.extend(loader(raw_dir))
    return records
