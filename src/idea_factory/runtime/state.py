"""共享状态层 —— 动态信号源的地基（纯 stdlib、文件交接、零 token）。

两个文件型 store，由零 token 的采集步维护，让三源从"读快照"升级为"记住历史、只取增量"：

* :class:`SeenStore`     —— 跨天去重：记住每个信号指纹是否见过、出现过几次。
* :class:`SignalHistory` —— 趋势序列：按"话题 × 日期"累计计数，喂给 :mod:`idea_core.trends`。

都落在 ``data/state/`` 下的 jsonl（gitignored）。写入原子化（tmp + os.replace）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(tmp, path)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


@dataclass
class SeenStore:
    """跨天去重。每条记录：{dedup_key, first_seen, last_seen, hit_count}。

    ``hit_count`` 同时是"升温"信号：同一指纹反复出现说明这个话题在持续冒头。
    """

    path: Path
    _by_key: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "SeenStore":
        path = Path(path)
        store = cls(path=path)
        for rec in _read_jsonl(path):
            store._by_key[rec["dedup_key"]] = rec
        return store

    def is_seen(self, dedup_key: str) -> bool:
        return dedup_key in self._by_key

    def observe(self, dedup_key: str, on: str) -> bool:
        """登记一次出现。返回 True 表示这是**新**指纹（之前没见过）。"""
        rec = self._by_key.get(dedup_key)
        if rec is None:
            self._by_key[dedup_key] = {
                "dedup_key": dedup_key,
                "first_seen": on,
                "last_seen": on,
                "hit_count": 1,
            }
            return True
        rec["last_seen"] = on
        rec["hit_count"] += 1
        return False

    def hit_count(self, dedup_key: str) -> int:
        rec = self._by_key.get(dedup_key)
        return rec["hit_count"] if rec else 0

    def keys(self) -> set[str]:
        return set(self._by_key)

    def save(self) -> None:
        lines = [json.dumps(rec, ensure_ascii=False) for rec in self._by_key.values()]
        _atomic_write_lines(self.path, lines)


@dataclass
class SignalHistory:
    """趋势时间序列。每条：{topic, date, count}（按话题 × 日累计）。"""

    path: Path
    # (topic, date) -> count
    _counts: dict[tuple[str, str], int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "SignalHistory":
        path = Path(path)
        hist = cls(path=path)
        for rec in _read_jsonl(path):
            hist._counts[(rec["topic"], rec["date"])] = rec["count"]
        return hist

    def add(self, topic: str, on: str, count: int = 1) -> None:
        if not topic:
            return
        self._counts[(topic, on)] = self._counts.get((topic, on), 0) + count

    def dates(self) -> list[str]:
        return sorted({d for (_t, d) in self._counts})

    def series(self, topic: str, window: int = 30, end: str | None = None) -> list[int]:
        """返回某话题最近 ``window`` 天的逐日计数（按日期升序，缺失日补 0）。

        ``end`` 为序列末尾日期（默认取该话题最新有数据的日期）；用全局日历的
        连续日期，保证 z-score 的窗口是等间隔的。
        """
        from datetime import date, timedelta

        topic_dates = sorted(d for (t, d) in self._counts if t == topic)
        if not topic_dates:
            return []
        end_d = date.fromisoformat(end) if end else date.fromisoformat(topic_dates[-1])
        days = [end_d - timedelta(days=i) for i in range(window - 1, -1, -1)]
        return [self._counts.get((topic, d.isoformat()), 0) for d in days]

    def topics(self) -> set[str]:
        return {t for (t, _d) in self._counts}

    def save(self) -> None:
        lines = [
            json.dumps({"topic": t, "date": d, "count": c}, ensure_ascii=False)
            for (t, d), c in sorted(self._counts.items())
        ]
        _atomic_write_lines(self.path, lines)
