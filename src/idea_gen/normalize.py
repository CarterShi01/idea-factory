"""Stage 2 -- normalize raw records into structured :class:`Signal` objects.

Two jobs beyond field-mapping:

1. **Abstract the pain.** We lift a ``pain_statement`` ("who struggles with
   what, in which situation") out of the raw title/text so the generate stage
   reasons about the underlying need rather than a surface headline.
2. **Assign stable identity.** ``id`` is a content hash so re-running on the
   same input is idempotent; ``dedup_key`` is a lexical fingerprint the dedup
   stage uses to spot near-duplicates.
"""

from __future__ import annotations

import hashlib
import re

from idea_core.models import (
    CONFIDENCE_REAL,
    SOURCE_EXTERNAL,
    Signal,
)

_DEFAULT_DATE = "1970-01-01"
# 英文按词、中文(CJK)按单字切分 —— 让中文信号也能得到有区分度的指纹/近重判断。
_WORD_RE = re.compile(r"[a-z0-9]+|[一-鿿]")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with",
    "is", "are", "be", "that", "this", "it", "as", "by", "at", "from",
    "their", "they", "you", "your", "we", "our", "i",
}


def _stable_id(source_name: str, title: str, url: str | None) -> str:
    basis = f"{source_name}|{title.strip().lower()}|{url or ''}".encode("utf-8")
    return hashlib.sha1(basis).hexdigest()[:12]


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


def _dedup_key(text: str) -> str:
    """Order-independent lexical fingerprint of the most salient tokens."""
    salient = sorted(set(_tokens(text)))
    return hashlib.sha1(" ".join(salient).encode("utf-8")).hexdigest()[:16]


def _pain_statement(raw: dict) -> str:
    """Lift an abstracted pain statement from a raw record.

    Prefers an explicit ``pain`` field; otherwise falls back to a templated
    phrasing built from the target user and the title/text.
    """
    explicit = (raw.get("pain") or "").strip()
    if explicit:
        return explicit
    who = (raw.get("target_user") or "用户").strip()
    what = (raw.get("title") or raw.get("text") or "").strip()
    return f"{who}在「{what}」上遇到困扰" if what else ""


def normalize_record(raw: dict) -> Signal:
    source = raw.get("source", SOURCE_EXTERNAL)
    source_name = raw.get("source_name", source)
    title = (raw.get("title") or raw.get("text") or "").strip()
    raw_text = (raw.get("text") or raw.get("title") or "").strip()
    url = raw.get("url")
    pain = _pain_statement(raw)
    fingerprint = pain or title or raw_text

    topic = (raw.get("category") or "").strip() or (raw.get("source_name") or source)
    return Signal(
        topic=topic,
        id=_stable_id(source_name, title, url),
        source=source,
        source_name=source_name,
        title=title,
        raw_text=raw_text,
        observed_on=raw.get("observed_on") or raw.get("date") or _DEFAULT_DATE,
        pain_statement=pain,
        dedup_key=_dedup_key(fingerprint),
        url=url,
        category=raw.get("category"),
        confidence=raw.get("confidence", CONFIDENCE_REAL),
    )


def normalize(records: list[dict]) -> list[Signal]:
    return [normalize_record(r) for r in records]
