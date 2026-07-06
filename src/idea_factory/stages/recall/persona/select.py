"""源③ 人群挑选 + 价值打分(纯函数、零 token)。

商业内核:**先找痛点才能赚钱** → 不凭空造人群,而是"按价值挑高价值人群 → 在其中找
真实痛点"。

两步:
- **动态全选**:`flatten_leaves` 把整棵 taxonomy 拉平成所有叶子人群(不漏任何人群)。
- **细分挑选**:`select_segments` 按 `segment_priority`(可变现先验 + 触达 + 真实趋势
  证据)× 久未挖探索奖励,只挑 Top-N 高价值细分人群(控 token/噪声)。

`persona_value` 是"人群×痛点"的四维价值分,用于挖到痛点后排序(对接 ranks/idea-eval)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
import os
from datetime import date
from pathlib import Path

_SEED_TAXONOMY = Path(__file__).resolve().parent / "taxonomy.json"


def _default_taxonomy_path() -> Path:
    """种子人群文件:优先环境变量 ``IDEA_PERSONA_TAXONOMY``(『你配置的』人群池,
    可指向仓外任意 JSON),否则用随源码分发的示例种子。"""
    override = os.environ.get("IDEA_PERSONA_TAXONOMY")
    return Path(override) if override else _SEED_TAXONOMY


@dataclass
class Segment:
    id: str
    label: str
    parent: str | None = None
    axes: dict = field(default_factory=dict)
    reachability: float = 0.5
    monetizability_prior: float = 0.5
    evidence_topics: list[str] = field(default_factory=list)
    last_mined_on: str = "1970-01-01"
    children: list[str] = field(default_factory=list)

    @property
    def is_leaf(self) -> bool:
        return not self.children


def load_taxonomy(path: str | Path | None = None, derived_path: str | Path | None = None) -> list[Segment]:
    """加载种子人群;若给定 ``derived_path`` 且存在,合并自动派生的人群(去重 by id)。"""
    p = Path(path) if path else _default_taxonomy_path()
    data = json.loads(p.read_text(encoding="utf-8"))
    base = [Segment(**{k: v for k, v in s.items() if k in Segment.__annotations__}) for s in data.get("segments", [])]
    if derived_path and Path(derived_path).exists():
        from .derive import load_derived

        seen = {s.id for s in base}
        base += [s for s in load_derived(derived_path) if s.id not in seen]
    return base


def flatten_leaves(segments: list[Segment]) -> list[Segment]:
    """动态全选:返回所有叶子人群(被挖的最小粒度),不漏。"""
    return [s for s in segments if s.is_leaf]


def _days_between(a: str, b: str) -> int:
    try:
        return abs((date.fromisoformat(b) - date.fromisoformat(a)).days)
    except (ValueError, TypeError):
        return 0


def _evidence_trend(seg: Segment, history, today: str | None = None) -> float:
    """这个人群的 evidence_topics 在源①真实信号里"在涨"的程度(0-1)。"""
    if history is None or not seg.evidence_topics:
        return 0.0
    from idea_factory.runtime.trends import classify

    speeds = []
    for topic in seg.evidence_topics:
        series = history.series(topic, window=14, end=today)
        if series:
            _status, speed = classify(series)
            speeds.append(speed)
    return max(speeds) if speeds else 0.0


def segment_priority(seg: Segment, history=None, today: str | None = None) -> float:
    """细分挑选用的人群优先级:可变现先验 + 触达 + 真实趋势证据,再乘久未挖探索奖励。"""
    today = today or date.today().isoformat()
    base = (
        0.45 * seg.monetizability_prior
        + 0.25 * seg.reachability
        + 0.30 * _evidence_trend(seg, history, today)
    )
    # 久未挖的人群给探索加成(防止每轮只挖同几个),30 天封顶 +50%
    staleness = min(_days_between(seg.last_mined_on, today), 60) / 60.0
    return round(base * (1.0 + 0.5 * staleness), 4)


def select_segments(
    segments: list[Segment],
    history=None,
    n: int = 4,
    today: str | None = None,
) -> list[Segment]:
    """全选 → 按优先级 + 探索奖励 → 取 Top-N 细分人群。"""
    leaves = flatten_leaves(segments)
    ranked = sorted(leaves, key=lambda s: (-segment_priority(s, history, today), s.id))
    return ranked[:n]


def persona_value(
    monetizability: float,
    pain_severity: float,
    reachability: float,
    competition: float,
) -> float:
    """人群×痛点 的四维价值分(先找能赚钱的痛点)。

    可变现性(0.35) + 痛点严重度(0.30) + 触达(0.20, =1-触达难度=reachability) - 竞争(0.15)
    """
    return round(
        0.35 * monetizability
        + 0.30 * pain_severity
        + 0.20 * reachability
        - 0.15 * competition,
        4,
    )
