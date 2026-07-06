"""⑦portfolio 的打散:把精排幸存者选成一个**组合**(纯代码,零 token)。

来源桶配额(中文为主)+ 创始人边单边上限 + 近重去聚类,选出终端 UI_N 组合排到
列表头部;不改判决,只改顺序。

⚠️ 本文件的分词器(``[\\w一-鿿]+`` 连串)与 runtime.textsim 故意不同——统一会
静默改变打散顺序(见 textsim 模块注)。
"""

from __future__ import annotations

import re

from idea_factory.contract.models import KILL, Evaluation, bucket_of

_EDGE_VOCAB = {
    "蒙语": ("蒙语", "蒙古", "蒙文", "内蒙", "蒙汉"),
    "安全云": ("安全云", "安全厂商", "云厂商", "等保", "云安全", "secops"),
    "出海硬件": ("出海", "硬件", "中东", "跨境", "海外"),
    "医疗心理": ("慢病", "医院", "医生", "心理", "焦虑", "失眠", "卫生"),
}


def _edge_of(idea: dict, source: str) -> str:
    """把候选归到一个『创始人边』桶,供打散做单边上限(防终端 20 全是同一边)。"""
    blob = f"{idea.get('title','')} {idea.get('target_user','')} {idea.get('pain','')}".lower()
    for edge, terms in _EDGE_VOCAB.items():
        if any(t in blob for t in terms):
            return edge
    return "英文市场" if source == "external_event" else "其它中文"


def _tok(s: str) -> set:
    return set(re.findall(r"[\w一-鿿]+", (s or "").lower()))


def _jac(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a and b) else 0.0


def _load_funnel_diversify() -> dict:
    from idea_factory.runtime.config import load_funnel

    default = {"ui_n": 20, "zh_min": 14, "en_max": 6, "per_edge_cap": 6, "dedup_jaccard": 0.6}
    try:
        cfg = load_funnel()
        if cfg:
            d = cfg.get("diversify", {}) or {}
            q = d.get("ui_quota", {}) or {}
            n = int((cfg.get("cut_sizes", {}) or {}).get("ui_n", default["ui_n"]))
            return {
                "ui_n": n,
                "zh_min": int(q.get("zh_min", default["zh_min"])),
                "en_max": int(q.get("en_max", default["en_max"])),
                "per_edge_cap": int(d.get("per_edge_cap", default["per_edge_cap"])),
                "dedup_jaccard": float(d.get("dedup_jaccard", default["dedup_jaccard"])),
            }
    except Exception:  # noqa: BLE001
        pass
    return default


def diversify_select(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    cfg: dict | None = None,
) -> list[Evaluation]:
    """打散:把精排幸存者(非 kill)按『来源桶配额 + 单边上限 + 近重去聚类』选出终端 UI_N 组合,
    排到列表**头部**(组合序),其余幸存者、再 kill 随后。WebUI / top3 读头部即得多样化的 20。

    中英混合的落点:``en_max`` 硬顶英文桶(→ 中文自然 ≥ zh_min),单边上限防"一色蒙语"。
    幸存者不足 UI_N 时放宽配额回填,保证长度。不改判决,只改**顺序**。
    """
    cfg = cfg or _load_funnel_diversify()

    survivors = [e for e in evaluations if e.verdict != KILL]
    killed = [e for e in evaluations if e.verdict == KILL]
    survivors.sort(key=lambda e: (-e.eval_score, e.idea_id))
    ui_n, zh_min, en_max = cfg["ui_n"], cfg["zh_min"], cfg["en_max"]
    edge_cap, dj = cfg["per_edge_cap"], cfg["dedup_jaccard"]

    def _bkt(e):
        return bucket_of(ideas_by_id.get(e.idea_id, {}).get("source", ""))

    def _pick_bucket(pool: list, n: int) -> list:
        """从(已按分排序的)桶里取 n 条:先按 单边上限 + 近重去聚类 选,不够再放宽补到 n。"""
        chosen: list = []
        parked: list = []
        edge_count: dict[str, int] = {}
        seen: list[set] = []
        for e in pool:
            if len(chosen) >= n:
                parked.append(e); continue
            idea = ideas_by_id.get(e.idea_id, {})
            edge = _edge_of(idea, idea.get("source", ""))
            toks = _tok(f"{e.title} {idea.get('pain','')}")
            if edge_count.get(edge, 0) >= edge_cap or any(_jac(toks, s) >= dj for s in seen):
                parked.append(e); continue
            chosen.append(e); seen.append(toks)
            edge_count[edge] = edge_count.get(edge, 0) + 1
        if len(chosen) < n:  # 严格约束不够 → 放宽 edge_cap/dedup 补到 n
            chosen += parked[: n - len(chosen)]
        return chosen

    zh_all = [e for e in survivors if _bkt(e) == "zh"]
    en_all = [e for e in survivors if _bkt(e) == "en"]

    # 配额驱动『中文为主』:目标 zh_min 中 + en_max 英;某桶不够,另一桶补足 ui_n。
    en_target = min(en_max, len(en_all))
    zh_target = min(len(zh_all), ui_n - en_target)
    en_target = min(len(en_all), ui_n - zh_target)  # zh 不足时英文回补

    head = _pick_bucket(zh_all, zh_target) + _pick_bucket(en_all, en_target)
    head_ids = {id(e) for e in head}
    # 头部按分排序(最好的在最前),其余幸存者、再 kill 随后
    head.sort(key=lambda e: (-e.eval_score, e.idea_id))
    rest = [e for e in survivors if id(e) not in head_ids]
    return head + rest + killed
