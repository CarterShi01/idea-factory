"""源③ 人群派生:从真实信号/候选里反复出现的 target_user 自动登记为新人群。

种子人群在 src 的 taxonomy.json(只读);派生人群落在 data/state/derived_segments.json
(gitignored、可增长),由 load_taxonomy 合并。这样"动态全选"每轮都能纳入新冒头的人群。
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from .select import Segment


def _get(item, key: str):
    return getattr(item, key, None) if not isinstance(item, dict) else item.get(key)


def _slug(label: str) -> str:
    return "derived." + hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]


def derive_segments(items, known_labels: set[str], min_count: int = 2) -> list[Segment]:
    """统计 items 的 target_user,出现 >= min_count 且不在 known_labels 的登记为新叶子人群。"""
    counts: Counter[str] = Counter()
    topics: dict[str, set] = defaultdict(set)
    for it in items:
        tu = (_get(it, "target_user") or "").strip()
        if not tu:
            continue
        counts[tu] += 1
        cat = _get(it, "category")
        if cat:
            topics[tu].add(str(cat))
    new: list[Segment] = []
    for label, c in counts.items():
        if c >= min_count and label not in known_labels:
            new.append(Segment(
                id=_slug(label), label=label, parent="derived",
                reachability=0.5, monetizability_prior=0.5,
                evidence_topics=sorted(topics[label])[:5],
                last_mined_on="1970-01-01", children=[],
            ))
    return new


def load_derived(path: str | Path) -> list[Segment]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [Segment(**{k: v for k, v in s.items() if k in Segment.__annotations__}) for s in data]


def save_derived(segments: list[Segment], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=2), encoding="utf-8")


def update_derived(items, base_segments: list[Segment], path: str | Path, min_count: int = 2) -> list[Segment]:
    """合并已有派生 + 本轮新派生,去重后持久化。返回最新派生列表。"""
    existing = load_derived(path)
    known = {s.label for s in base_segments} | {s.label for s in existing}
    fresh = derive_segments(items, known, min_count=min_count)
    merged = existing + fresh
    if fresh:
        save_derived(merged, path)
    return merged
