"""三源交叉自喂(纯函数、零 token)—— 旧仓 match.py 的继承者。

核心:用源①的真实信号去**佐证**源③的合成痛点、**加权**源②的脑海 idea。匹配用
CJK-aware 的 token-set + Jaccard(复用 dedup 的切分),不引入 embedding(守住 stdlib/离线)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from idea_factory.runtime.textsim import jaccard, tokens as _token_set


@dataclass
class Corroboration:
    real_hits: int = 0
    supporting: list[str] = field(default_factory=list)   # 佐证信号的标题
    trend: str = "none"                                   # 佐证信号里最强的趋势状态


def _record_text(r: dict) -> str:
    return " ".join(
        str(r.get(k, "")) for k in ("title", "pain", "pain_statement", "text", "category")
    )


def corroborate(pain_text: str, real_records: list[dict], threshold: float = 0.12) -> Corroboration:
    """在源①真实信号里找与该痛点重叠的信号。返回命中数 + 佐证标题 + 最强趋势。"""
    pt = _token_set(pain_text)
    if not pt:
        return Corroboration()
    order = {"rising": 3, "steady": 2, "peaked": 1, "none": 0}
    best_trend = "none"
    supporting: list[str] = []
    for r in real_records:
        if jaccard(pt, _token_set(_record_text(r))) >= threshold:
            supporting.append(str(r.get("title", "")))
            t = str(r.get("trend_status", "none"))
            if order.get(t, 0) > order.get(best_trend, 0):
                best_trend = t
    return Corroboration(real_hits=len(supporting), supporting=supporting[:5], trend=best_trend)
