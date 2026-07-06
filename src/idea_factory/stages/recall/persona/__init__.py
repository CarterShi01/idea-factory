"""源③ 人群系统:可增长 taxonomy + 动态全选/细分挑选 + 四维价值打分。"""

from .select import (
    Segment,
    flatten_leaves,
    load_taxonomy,
    persona_value,
    segment_priority,
    select_segments,
)

__all__ = [
    "Segment",
    "load_taxonomy",
    "flatten_leaves",
    "segment_priority",
    "persona_value",
    "select_segments",
]
