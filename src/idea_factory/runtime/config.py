"""Unified config loading (founder / funnel / sources).

One place owns the path conventions + env overrides that used to be scattered
across factors.py / ranks.py / evaluate.py / collect.py:

* ``config/founder.json``  -- env ``IDEA_FOUNDER_PROFILE``  (founder profile)
* ``config/funnel.json``   -- env ``IDEA_FUNNEL_CONFIG``    (funnel cut sizes / weights / triage)
* ``config/sources.json``  -- env ``IDEA_SOURCES_CONFIG``   (recall channel toggles)

founder/funnel default to CWD-relative paths (running from the repo root is the
convention, and tests monkeypatch the env vars); sources anchors to the repo
root via ``__file__`` so Studio (which runs with its own CWD) still finds it.
All loaders fail soft: a missing/broken file returns ``{}`` or the given
default -- config absence must never crash the offline pipeline.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# src/idea_factory/runtime/config.py -> parents[3] == repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


def founder_path() -> Path:
    return Path(os.environ.get("IDEA_FOUNDER_PROFILE", "config/founder.json"))


def funnel_path() -> Path:
    return Path(os.environ.get("IDEA_FUNNEL_CONFIG", "config/funnel.json"))


def sources_path() -> Path:
    return Path(os.environ.get("IDEA_SOURCES_CONFIG", REPO_ROOT / "config" / "sources.json"))


def _load_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        pass
    return {}


def load_founder() -> dict:
    return _load_json(founder_path())


def load_funnel() -> dict:
    return _load_json(funnel_path())


def load_sources(default: dict | None = None) -> dict:
    cfg = _load_json(sources_path())
    if cfg:
        return cfg
    # 兜底:三个静态源默认开,联网源默认关(与旧 collect.py 行为一致)
    return default if default is not None else {"static_external": {}, "brain": {}, "persona": {}}
