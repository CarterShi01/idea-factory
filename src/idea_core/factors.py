"""The factor library -- the heart of the quant analogy.

Each factor is a **pure function** ``IdeaCandidate -> float in [0, 1]``. No I/O,
no randomness, no global state, so every factor is independently unit-testable
and versionable.

These definitions are the single source of truth and are meant to be shared
verbatim with the ``idea-evl`` repo. The freqtrade lesson from the research: if
the generation side and the evaluation side compute factors differently, the
back-tested "promising" ideas turn out wrong in production. Same factors, both
sides.

Round 2(投资人复评严重度②):上一版因子是**开关不是打分**——市场新鲜度 12 个 1.0、
护城河 13 个 0.1、竞争稀缺度 14 个 1.0。根因是每个因子都是『命中一个关键词就跳到
极值』的二值化阈值。本轮把每个因子改成**连续、有区分度**的判别式:多档证据加权、
词频饱和曲线、不同壁垒类型分别计分,使同一批候选产出**分布**而非常数。

Round 2(投资人复评严重度①):pain_intensity 不再只数痛点词——它现在按**证据强度**
打分(信号 confidence、是否有付费意愿信号、是否疑似臆想/编造痛点),把『凭空臆想/
与信号无关』的伪痛点压到低分,让评估侧的击杀门能据此说不。

The factors are transparent heuristics. They are placeholders for later
model-based factors -- the *interface* (pure ``candidate -> float``) is what
matters and is designed to outlive the heuristics.
"""

from __future__ import annotations

from .models import CONFIDENCE_REAL, CONFIDENCE_SYNTHETIC, IdeaCandidate

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
# Strong evidence the pain is *paid for today* — willingness-to-pay signal.
# These are the highest-quality pain signal; their presence lifts pain_intensity.
_WILLINGNESS_TO_PAY = {
    "pay for", "paying for", "paid tool", "subscription", "per month",
    "/month", "/mo", "budget", "expensive", "we pay", "currently pay",
    "hire", "hired", "outsource", "freelancer", "consultant",
    "付费", "付钱", "愿意付", "订阅", "每月", "预算", "外包", "花钱买",
    "雇人", "请人", "已经在用", "正在用", "在花钱", "成本高",
}
# Phrasing that betrays an *imagined* / fabricated pain rather than an observed
# one — speculation markers. Their presence discounts pain_intensity.
_SPECULATIVE = {
    "imagine", "what if", "could", "might want", "would be nice",
    "people probably", "users may", "i think users", "should want",
    "nice to have", "maybe", "perhaps", "in theory", "hypothetically",
    "或许", "也许", "可能想", "应该会", "如果能", "如果可以", "想象",
    "据我推测", "我觉得用户", "理论上", "假设用户", "说不定", "锦上添花",
}
# Real moat by *type* — each distinct type contributes; a candidate that has data
# moat AND network effects is more defensible than one with a single hint.
_MOAT_DATA = {
    "proprietary data", "dataset", "data moat", "unique data", "labeled data",
    "private data", "first-party data", "accumulating data",
    "专有数据", "数据集", "私有数据", "独占数据", "数据壁垒", "数据积累", "标注数据",
}
_MOAT_NETWORK = {
    "network effect", "network effects", "two-sided", "marketplace dynamics",
    "community", "user-generated", "viral", "more users",
    "网络效应", "双边", "社区", "用户生成", "越多人用", "用户网络",
}
_MOAT_INTEGRATION = {
    "deep integration", "integration", "embedded in", "workflow lock-in",
    "switching cost", "system of record", "sticky", "data sync",
    "深度集成", "嵌入工作流", "切换成本", "工作流锁定", "记录系统", "粘性",
}
_MOAT_DOMAIN = {
    "vertical", "domain expertise", "niche", "regulatory", "compliance moat",
    "specialized", "industry-specific", "hard-won knowledge",
    "垂直", "领域知识", "细分", "专业壁垒", "行业特定", "专有工作流", "护城河",
}
# Hints of a crowded, undifferentiated space. Graded by how commodity it is.
_COMMODITY = {  # near-zero differentiation, heavy penalty
    "another", "clone", "generic", "url shortener", "todo app", "to-do app",
    "wrapper", "crud app", "boilerplate",
    "又一个", "克隆", "通用", "套壳", "山寨", "待办应用", "脚手架",
}
_CROWDED = {  # busy but not necessarily commodity, lighter penalty
    "chatbot", "todo", "to-do", "note", "note-taking", "dashboard",
    "summarizer", "summary tool", "ai assistant", "productivity app",
    "聊天机器人", "待办", "笔记", "看板", "总结工具", "助手", "效率工具", "同质化",
}
# Complexity, tiered by how non-solo the build is.
_COMPLEXITY_HEAVY = {  # essentially un-buildable solo
    "marketplace", "hardware", "logistics", "two-sided", "blockchain",
    "supply chain", "warehouse", "fleet", "on-premise rollout",
    "硬件", "物流", "双边", "区块链", "供应链", "仓储", "私有部署",
}
_COMPLEXITY_MED = {  # buildable but a real drag for one person
    "enterprise", "compliance", "hipaa", "regulat", "payroll", "soc2",
    "sso", "audit log", "multi-tenant", "on-premise",
    "企业级", "合规", "监管", "牌照", "线下", "多租户", "审计", "权限体系",
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


def _has_any(text: str, vocab: set[str]) -> bool:
    return any(term in text for term in vocab)


def _saturating(hits: int, *, half: float) -> float:
    """Map a hit count to (0, 1) with diminishing returns (no hard cliff).

    ``half`` hits → 0.5; more hits keep rising but never reach a flat 1.0 and
    never snap to it from a single keyword. This is what kills the old binary
    behaviour: 1 hit and 5 hits now land at clearly different scores.
    """
    if hits <= 0:
        return 0.0
    return hits / (hits + half)


# --- factors --------------------------------------------------------------

_TREND_BONUS = {"rising": 0.25, "steady": 0.0, "peaked": -0.25}


def market_freshness(c: IdeaCandidate) -> float:
    """Is the idea riding a currently-fresh topic? Higher = fresher.

    Continuous: a saturating keyword score (so 1 trend word ≠ many) ⊕ the real
    trend signal (rising/peaked + growth_speed). The old version saturated to
    1.0 the moment it saw a couple of trend words, hence the 12×1.0 cluster.
    """
    kw = _saturating(_count_hits(c.text(), _TRENDING), half=3.0)
    base = 0.15 + 0.7 * kw  # spread into [0.15, 0.85] from keywords alone
    bonus = _TREND_BONUS.get(getattr(c, "trend_status", "steady"), 0.0)
    bonus += 0.15 * float(getattr(c, "growth_speed", 0.0) or 0.0)
    return round(max(0.0, min(1.0, base + bonus)), 4)


def pain_intensity(c: IdeaCandidate) -> float:
    """How sharp AND well-evidenced is the pain? Higher = sharper + realer.

    Round 2(严重度①):this is now an **evidence-weighted** score, not a raw
    pain-word count. The investor's complaint was fabricated pains ("按语音语调
    判优先级") still scoring well. We combine:

    * sharpness  — saturating count of pain words across pain + solution;
    * willingness-to-pay — a strong real-demand signal (someone pays today);
    * confidence — synthetic (persona-simulated) pains are discounted unless
      they also carry a paid/strong signal (the "needs ≥1 real corroboration"
      rule from the roadmap, applied as a score, not a hard flag);
    * speculation penalty — imagined/"would be nice" phrasing drags it down;
    * vague-pain penalty — a one-liner with no concrete pain word is treated as
      an un-evidenced pain (likely fabricated), not a sharp one.

    The result is a genuinely discriminating signal the eval kill-gate keys on.
    """
    pain_text = (c.pain or "").lower()
    sol_text = (c.solution or "").lower()
    blob = f"{pain_text} {sol_text}"

    sharpness = _saturating(_count_hits(blob, _PAIN), half=2.0)  # 0..~1

    # Strong, concrete demand signal: someone already pays / hires for this.
    has_wtp = _has_any(blob, _WILLINGNESS_TO_PAY)
    wtp = 0.25 if has_wtp else 0.0

    # Base from observed sharpness; willingness-to-pay lifts it.
    score = 0.7 * sharpness + wtp

    # Confidence: synthetic persona pains are suspect (investor: persona 需佐证).
    # Discount them unless a concrete paid/demand signal corroborates.
    if getattr(c, "confidence", CONFIDENCE_REAL) == CONFIDENCE_SYNTHETIC and not has_wtp:
        score *= 0.6

    # Speculation penalty: "imagine / would be nice / 或许用户想" => fabricated.
    spec = _count_hits(blob, _SPECULATIVE)
    if spec:
        score -= min(0.4, 0.2 * spec)

    # Vague-pain penalty: a pain statement with zero pain words and no demand
    # signal is an un-evidenced (likely invented) pain — floor it low.
    if _count_hits(pain_text, _PAIN) == 0 and not has_wtp:
        score = min(score, 0.2)

    return round(max(0.0, min(1.0, score)), 4)


def build_cost(c: IdeaCandidate) -> float:
    """Solo-buildability. Higher = cheaper/faster for a one-person company.

    Tiered: heavy non-solo concerns (marketplace/hardware) cost more than
    medium ones (compliance/SSO). Graded penalties instead of a flat 0.25/hit.
    """
    text = c.text()
    heavy = _count_hits(text, _COMPLEXITY_HEAVY)
    med = _count_hits(text, _COMPLEXITY_MED)
    penalty = 0.35 * heavy + 0.18 * med
    return round(max(0.0, 1.0 - penalty), 4)


def moat_signal(c: IdeaCandidate) -> float:
    """Any hint of defensibility? Higher = more moat.

    Round 2(严重度②):the old version was 0.1 unless a single keyword hit, then
    jumped — hence 13×0.1, 2×1.0. Now it scores by **distinct moat types**
    present (data / network / integration / domain). Having two kinds of moat
    beats having one; a bare idea sits near a small floor, not at a hard 0.1.
    """
    text = c.text()
    types_present = sum(
        1
        for vocab in (_MOAT_DATA, _MOAT_NETWORK, _MOAT_INTEGRATION, _MOAT_DOMAIN)
        if _has_any(text, vocab)
    )
    # 0 types -> 0.1 floor; each distinct type adds, saturating toward 1.0.
    return round(0.1 + 0.9 * _saturating(types_present, half=1.5), 4)


def competition_density(c: IdeaCandidate) -> float:
    """Higher = *less* crowded (a better score).

    Round 2(严重度②):was 1.0 unless a crowded word hit (14×1.0). Now graded:
    commodity terms (clone/url shortener) penalize hard, merely-busy terms
    (chatbot/dashboard) penalize lightly, and absence of either gives a high —
    but not maxed — score, so unremarkable ideas don't all pin at 1.0.
    """
    text = c.text()
    commodity = _count_hits(text, _COMMODITY)
    crowded = _count_hits(text, _CROWDED)
    penalty = 0.35 * commodity + 0.15 * crowded
    base = 0.85  # a generic-but-not-flagged idea is "fairly open", not pristine
    return round(max(0.0, min(1.0, base - penalty)), 4)


def distribution_fit(c: IdeaCandidate) -> float:
    """Can this founder reach these users? Higher = more reachable.

    Saturating over reachable-audience mentions (weighting target_user double,
    since that's the primary channel signal). Spread, not binary.
    """
    user_hits = 2 * _count_hits((c.target_user or "").lower(), _REACHABLE)
    body_hits = _count_hits(c.text(), _REACHABLE)
    hits = user_hits + body_hits
    return round(0.1 + 0.85 * _saturating(hits, half=2.5), 4)


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
