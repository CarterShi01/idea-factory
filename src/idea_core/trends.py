"""趋势检测 —— 纯 stdlib 的滑动窗口 + Moving Z-Score 突增检测。

"动态"的精髓不是"有什么"，而是"什么在涨"。把 :class:`idea_core.state.SignalHistory`
的逐日话题计数喂进来，输出 ``rising / steady / peaked`` + ``growth_speed``（0-1），
再回喂 ``market_freshness`` 因子（见 idea_core.factors）。
"""

from __future__ import annotations

import statistics

RISING = "rising"
STEADY = "steady"
PEAKED = "peaked"


def moving_zscore(series: list[float], lag: int = 8, threshold: float = 2.0, influence: float = 0.3) -> list[float]:
    """逐点 z-score。新突增点以 ``influence`` 衰减计入后续阈值，避免一次尖峰污染整条基线。"""
    if len(series) <= lag:
        return [0.0] * len(series)
    zs = [0.0] * len(series)
    filtered = list(series[:lag])
    mean = statistics.fmean(filtered)
    std = statistics.pstdev(filtered) or 1e-9
    for i in range(lag, len(series)):
        dev = series[i] - mean
        if abs(dev) > threshold * std:
            zs[i] = dev / std
            filtered.append(influence * series[i] + (1 - influence) * filtered[-1])
        else:
            filtered.append(series[i])
        win = filtered[-lag:]
        mean = statistics.fmean(win)
        std = statistics.pstdev(win) or 1e-9
    return zs


def classify(series: list[int], lag: int = 8) -> tuple[str, float]:
    """把一条逐日计数序列分类为 rising/steady/peaked + growth_speed(0-1)。

    序列太短（冷启动、未填满窗口）时退化为 steady / 0，避免不可信判断。
    """
    if len(series) <= lag or sum(series) == 0:
        return STEADY, 0.0
    recent = moving_zscore(series, lag=lag)[-1]
    growth_speed = max(0.0, min(1.0, recent / 4.0))
    if recent >= 2.0:
        return RISING, round(growth_speed, 4)
    if recent <= -1.0:
        return PEAKED, round(growth_speed, 4)
    return STEADY, round(growth_speed, 4)
