"""The factor library -- the heart of the quant analogy.

Each factor is a **pure function** ``IdeaCandidate -> float in [0, 1]``. No I/O,
no randomness, no global state, so every factor is independently unit-testable
and versionable.

These definitions are the single source of truth and are meant to be shared
verbatim with the ``idea-evl`` repo. The freqtrade lesson from the research: if
the generation side and the evaluation side compute factors differently, the
back-tested "promising" ideas turn out wrong in production. Same factors, both
sides.

The MVP factors are transparent keyword heuristics. They are placeholders for
later model-based factors -- the *interface* (pure ``candidate -> float``) is
what matters and is designed to outlive the heuristics.
"""

from __future__ import annotations

from .models import IdeaCandidate

# --- keyword vocabularies -------------------------------------------------

# The vocabularies are bilingual (EN + 中文). Matching is plain substring
# containment, which works for Chinese (no word boundaries needed); the English
# terms never match Chinese text and vice-versa, so adding 中文 terms is purely
# additive and leaves English scoring unchanged.

# Topics currently in a fresh / rising window.
_TRENDING = {
    "ai", "agent", "agents", "llm", "rag", "copilot", "automation", "gpt",
    "embedding", "vector", "multimodal", "voice", "local-first", "privacy",
    "mcp", "fine-tune", "self-hosted",
    "智能体", "大模型", "自动化", "多模态", "语音", "隐私", "本地", "私有化",
    "向量", "检索增强", "微调", "副驾", "助手", "智能",
}
# Words that signal a real, sharp pain.
_PAIN = {
    "expensive", "costly", "manual", "manually", "tedious", "slow", "broken",
    "frustrat", "waste", "wasting", "hate", "painful", "hard", "difficult",
    "confusing", "unreliable", "clunky", "hours", "repetitive", "missing",
    "lack", "struggle", "annoying", "overwhelm", "error-prone",
    "昂贵", "手动", "手工", "繁琐", "低效", "浪费", "痛苦", "困难", "难以",
    "缺乏", "缺少", "麻烦", "耗时", "重复", "易错", "痛点", "不便", "头疼",
    "效率低", "花时间", "费时", "无法",
}
# Words that imply a heavy, non-solo build.
_COMPLEXITY = {
    "marketplace", "hardware", "logistics", "enterprise", "compliance",
    "hipaa", "two-sided", "regulat", "blockchain", "on-premise", "fleet",
    "supply", "warehouse", "payroll",
    "硬件", "物流", "企业级", "合规", "双边", "监管", "区块链", "私有部署",
    "供应链", "仓储", "牌照", "线下",
}
# Hints of defensibility / moat.
_MOAT = {
    "proprietary", "workflow", "integration", "dataset", "niche", "community",
    "network", "vertical", "domain", "fine-tune", "data",
    "专有", "工作流", "集成", "数据集", "细分", "社区", "网络效应", "垂直",
    "领域", "壁垒", "护城河", "私有数据",
}
# Hints of a crowded, undifferentiated space.
_CROWDED = {
    "another", "clone", "generic", "chatbot", "todo", "to-do", "note",
    "url shortener", "crud", "wrapper",
    "又一个", "克隆", "通用", "聊天机器人", "待办", "套壳", "山寨", "同质化",
}
# Users this particular founder (software, also investing) can actually reach.
_REACHABLE = {
    "developer", "developers", "indie", "founder", "founders", "investor",
    "investors", "engineer", "engineers", "software", "startup", "saas",
    "builder", "builders", "analyst", "technical",
    "开发者", "独立开发", "创始人", "投资人", "投资者", "工程师", "软件",
    "初创", "程序员", "技术", "站长", "团队", "独立开发者",
}


def _count_hits(text: str, vocab: set[str]) -> int:
    return sum(1 for term in vocab if term in text)


# --- factors --------------------------------------------------------------

_TREND_BONUS = {"rising": 0.3, "steady": 0.0, "peaked": -0.2}


def market_freshness(c: IdeaCandidate) -> float:
    """Is the idea riding a currently-fresh topic? Higher = fresher.

    Keyword heuristic ⊕ real trend signal: when the candidate carries a
    ``trend_status`` / ``growth_speed`` (dynamic mode), fold them in; otherwise
    (offline default) it degrades to the pure keyword score. Pure function either
    way, so gen and eval still compute the same factor.
    """
    kw = min(1.0, 0.1 + _count_hits(c.text(), _TRENDING) / 2.0)
    bonus = _TREND_BONUS.get(getattr(c, "trend_status", "steady"), 0.0)
    bonus += 0.2 * getattr(c, "growth_speed", 0.0)
    return max(0.0, min(1.0, kw + bonus))


def pain_intensity(c: IdeaCandidate) -> float:
    """How sharp is the underlying pain? Higher = sharper. Weighted most."""
    hits = _count_hits(c.pain.lower(), _PAIN)
    return min(1.0, hits / 4.0)


def build_cost(c: IdeaCandidate) -> float:
    """Solo-buildability. Higher = cheaper/faster for a one-person company."""
    penalty = 0.25 * _count_hits(c.text(), _COMPLEXITY)
    return max(0.0, 1.0 - penalty)


def moat_signal(c: IdeaCandidate) -> float:
    """Any hint of defensibility? Higher = more moat."""
    hits = _count_hits(c.text(), _MOAT)
    return min(1.0, 0.1 + hits / 2.0)


def competition_density(c: IdeaCandidate) -> float:
    """Higher = *less* crowded (a better score)."""
    penalty = 0.3 * _count_hits(c.text(), _CROWDED)
    return max(0.0, 1.0 - penalty)


def distribution_fit(c: IdeaCandidate) -> float:
    """Can this founder reach these users? Higher = more reachable."""
    hits = _count_hits((c.target_user + " " + c.text()).lower(), _REACHABLE)
    return min(1.0, 0.1 + hits / 2.0)


# Registry: name -> pure factor function. Iterate this everywhere so the set of
# factors is defined in exactly one place.
FACTORS = {
    "market_freshness": market_freshness,
    "pain_intensity": pain_intensity,
    "build_cost": build_cost,
    "moat_signal": moat_signal,
    "competition_density": competition_density,
    "distribution_fit": distribution_fit,
}

# Chinese display labels for the factor keys (keys stay English identifiers).
FACTOR_LABELS = {
    "market_freshness": "市场新鲜度",
    "pain_intensity": "痛点强度",
    "build_cost": "可落地性",
    "moat_signal": "护城河",
    "competition_density": "竞争稀缺度",
    "distribution_fit": "触达匹配度",
}


def label(name: str) -> str:
    return FACTOR_LABELS.get(name, name)


def compute_factors(c: IdeaCandidate) -> dict[str, float]:
    """Run every factor over a candidate, rounding for stable serialization."""
    return {name: round(fn(c), 4) for name, fn in FACTORS.items()}
