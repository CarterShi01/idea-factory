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
# Round 2(投资人复评严重度④):**无关付费谬误** — round1 实证 #4『用户买过第二大脑
# 类课程』被当成『愿为语音转 PRD 付费』。买课程 / 买书 / 订了个通用 SaaS,**不等于**愿为
# *本方案* 付费。这些是『邻近/泛化购买』标记:出现它们而没有针对本任务的直接付费/雇人信号
# 时,payment_signal 视为**编造的付费证据**并压低,而不是当真。
_IRRELEVANT_PAY = {
    "bought a course", "bought a book", "took a course", "online course",
    "watched tutorials", "follows influencers", "read a book", "signed up for a newsletter",
    "downloaded an app", "uses a free", "general saas", "similar product",
    "买过课程", "买了课", "上过课", "买了书", "看过教程", "关注了博主",
    "订阅了新闻", "下载过", "用过免费", "类似产品", "买过类似",
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
# Round 2(投资人复评严重度②:moat 几乎恒 0.1)。根因:旧词表太窄(只认 "proprietary data"
# 这种术语原话),真候选很少这样写,于是清一色落在 0.1 地板。这里把每类壁垒的词表扩到
# 覆盖**自然语言里描述同一壁垒的常见说法**(数据飞轮/越用越准/独占接入/领域 know-how),
# 让真正带壁垒的方案能被识别并按类型数量分级,同时保留"裸方案≈地板"的低分。
_MOAT_DATA = {
    "proprietary data", "dataset", "data moat", "unique data", "labeled data",
    "private data", "first-party data", "accumulating data", "data flywheel",
    "gets smarter", "improves with use", "more data", "historical data",
    "training corpus", "benchmark data", "compounding data",
    "专有数据", "数据集", "私有数据", "独占数据", "数据壁垒", "数据积累", "标注数据",
    "数据飞轮", "越用越准", "越用越好", "沉淀数据", "历史数据",
}
_MOAT_NETWORK = {
    "network effect", "network effects", "two-sided", "marketplace dynamics",
    "community", "user-generated", "viral", "more users", "each new user",
    "shared library", "crowdsourced", "benchmark against peers", "peer comparison",
    "网络效应", "双边", "社区", "用户生成", "越多人用", "用户网络", "众包",
    "共享库", "同行对标", "互相",
}
_MOAT_INTEGRATION = {
    "deep integration", "integration", "embedded in", "workflow lock-in",
    "switching cost", "system of record", "sticky", "data sync",
    "exclusive access", "official partner", "private api", "hard to replicate",
    "becomes the hub", "single source of truth",
    "深度集成", "嵌入工作流", "切换成本", "工作流锁定", "记录系统", "粘性",
    "独占接入", "官方合作", "成为枢纽", "难以复制",
}
_MOAT_DOMAIN = {
    "vertical", "domain expertise", "niche", "regulatory", "compliance moat",
    "specialized", "industry-specific", "hard-won knowledge", "know-how",
    "deep domain", "insider knowledge", "purpose-built for", "battle-tested",
    "垂直", "领域知识", "细分", "专业壁垒", "行业特定", "专有工作流", "护城河",
    "领域经验", "行业洞察", "深耕", "专为",
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
    "supply chain", "warehouse", "fleet", "on-premise rollout", "device",
    "firmware", "embedded device", "iot",
    "硬件", "物流", "双边", "区块链", "供应链", "仓储", "私有部署", "设备",
    "固件", "嵌入式",
}
_COMPLEXITY_MED = {  # buildable but a real drag for one person
    "enterprise", "compliance", "hipaa", "regulat", "payroll", "soc2",
    "sso", "audit log", "multi-tenant", "on-premise", "license", "kyc",
    "企业级", "合规", "监管", "牌照", "线下", "多租户", "审计", "权限体系",
    "实名", "风控",
}
# Round 2(投资人复评严重度②:"怎么可能每个都 100% 可落地"——build_cost 几乎全 1.0)。
# 根因:旧 build_cost **只减分**(命中重/中复杂度词才扣),而真实候选几乎不命中那批词,
# 于是清一色 1.0。真方案的成本来自具体实现负担:要接几个外部系统、要不要训练/自托管模型、
# 是否多端、是否碰合规/硬件。下面三组刻画这些**正向成本驱动**,让 build_cost 从一个非满分
# 的基线按真实负担铺开,而不是"无重词=满分"。
# 每接一个外部系统都是真实集成成本(鉴权/限流/字段对齐/它一改你就坏)。
_INTEGRATION = {
    "integrate", "integration", "api", "webhook", "oauth", "sync",
    "connector", "plugin for", "scrape", "scraping", "crawl", "third-party",
    "stripe", "github", "gmail", "slack", "notion", "salesforce", "jira",
    "集成", "对接", "接口", "回调", "抓取", "爬取", "同步", "插件接入",
    "第三方", "对账",
}
# 要自己训练 / 微调 / 自托管模型 = 数据 + GPU + 运维,绝非一周能搞定。
_MODEL_BUILD = {
    "train a model", "training", "fine-tune", "fine-tuning", "self-host",
    "self-hosted", "on-device model", "local llm", "host the model",
    "custom model", "label data", "annotation pipeline", "rlhf",
    "训练模型", "微调", "自托管", "本地大模型", "本地模型", "标注", "自研模型",
    "私有化部署模型",
}
# 多端(web+iOS+Android+桌面+插件)成倍工程量,一人公司的隐形税。
_MULTI_PLATFORM = {
    "ios", "android", "mobile app", "desktop app", "cross-platform",
    "browser extension", "chrome extension", "multi-platform", "native app",
    "全平台", "多端", "移动端", "桌面端", "浏览器扩展", "小程序", "客户端",
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


def payment_signal(c: IdeaCandidate) -> float:
    """How real is the *willingness to pay*? Higher = stronger paid demand.

    Round 2(投资人复评严重度④):round1 said pain_intensity and payment evidence
    were conflated, and that the alpha ranking under-weighted paid demand — the
    scarcest, most valuable signal. This factor pulls *willingness-to-pay* out
    into its own first-class axis so the ranker can weight it directly (round1's
    prescribed 0.25). It is deliberately **harder to fake** than a pain word:

    * direct paid demand — someone *currently pays / hires / outsources* for this
      exact job (saturating count, so multiple corroborations beat one);
    * irrelevant-payment penalty — the "bought a course ⇒ willing to pay" fallacy
      round1 flagged (#4). A generic / adjacent purchase with **no** direct paid
      signal for the actual task is treated as fabricated evidence and floored low;
    * speculation penalty — "would pay" / "people probably pay" is not evidence;
    * synthetic discount — a persona-simulated paid signal is worth less than an
      observed one (the ≥1 real corroboration rule), unless it cites a concrete
      hire/outsource/currently-pay fact.

    A candidate with no paid signal at all sits at a low floor (not zero — absence
    of evidence isn't proof of no demand, just an un-validated bet).
    """
    pain_text = (c.pain or "").lower()
    why_now = (getattr(c, "why_now", "") or "").lower()
    blob = f"{pain_text} {(c.solution or '').lower()} {why_now}"

    direct = _count_hits(blob, _WILLINGNESS_TO_PAY)
    irrelevant = _count_hits(blob, _IRRELEVANT_PAY)
    spec = _count_hits(blob, _SPECULATIVE)

    # No direct paid signal at all → low floor (un-validated demand).
    if direct == 0:
        base = 0.12
        # A bare adjacent purchase paraded as "proof" is *worse* than silence:
        # it's fabricated evidence. Drag it under the floor toward zero.
        if irrelevant:
            base = max(0.0, base - 0.06 * irrelevant)
        return round(base, 4)

    # Speculative phrasing co-occurring with a paid phrase usually *is* the paid
    # phrase ("would pay for" / "might pay for" / "或许愿意付费") — i.e. an imagined
    # payment, not an observed one. Treat it as essentially un-evidenced: collapse
    # to (just above) the no-signal floor rather than crediting it as real demand.
    if spec:
        return round(max(0.05, 0.18 - 0.04 * min(irrelevant, 2)), 4)

    # Real paid signal present: score by strength (saturating), from a real floor.
    score = 0.35 + 0.6 * _saturating(direct, half=2.0)

    # Irrelevant-purchase fallacy: each adjacent "proof" dilutes the real signal.
    if irrelevant:
        score -= min(0.3, 0.12 * irrelevant)
    # Synthetic persona paid signal is worth less than an observed one.
    if getattr(c, "confidence", CONFIDENCE_REAL) == CONFIDENCE_SYNTHETIC:
        score *= 0.75

    return round(max(0.05, min(1.0, score)), 4)


def build_cost(c: IdeaCandidate) -> float:
    """Solo-buildability. Higher = cheaper/faster for a one-person company.

    Round 2(投资人复评严重度②):the old version only *subtracted* for heavy/medium
    complexity words, and real candidates almost never hit those, so it pinned at
    1.0 for everyone ("怎么可能每个都 100% 可落地"). It now scores from a
    non-maxed base and subtracts for the *real* drivers of build effort, so the
    factor spreads into a distribution instead of being an on/off switch:

    * integrations — every external system to wire up (auth/rate-limit/field-mapping)
      is real work, and it breaks when the other side changes; counted with
      diminishing returns (the 1st integration costs more than the 5th marginally);
    * model build — training / fine-tuning / self-hosting a model is data + GPU + ops,
      not a one-week MVP;
    * multi-platform — web + iOS + Android + desktop + extension multiplies effort;
    * heavy/medium domain complexity — hardware/marketplace (un-buildable solo) and
      compliance/SSO/multi-tenant (a real drag), as before.

    The base is 0.9 (a clean single-surface tool is *cheap* but never "free"), and
    each driver pulls it down, floored at a small positive value.
    """
    text = c.text()
    integ = _count_hits(text, _INTEGRATION)
    model = _count_hits(text, _MODEL_BUILD)
    platform = _count_hits(text, _MULTI_PLATFORM)
    heavy = _count_hits(text, _COMPLEXITY_HEAVY)
    med = _count_hits(text, _COMPLEXITY_MED)

    penalty = 0.0
    # Integrations: saturating cost so a dozen keyword hits can't drive it to 0.
    penalty += 0.45 * _saturating(integ, half=2.0)
    # Model build is binary-ish but heavy: presence of any such signal is a big tax.
    penalty += 0.30 * _saturating(model, half=1.0)
    # Multi-platform: each additional surface, diminishing.
    penalty += 0.25 * _saturating(platform, half=1.5)
    # Domain complexity (unchanged drivers), now part of the same additive model.
    penalty += 0.35 * heavy + 0.18 * med

    return round(max(0.05, 0.9 - penalty), 4)


def moat_signal(c: IdeaCandidate) -> float:
    """Any hint of defensibility? Higher = more moat.

    Round 2(严重度②):the old version was 0.1 unless a single keyword hit, then
    jumped — hence 13×0.1, 2×1.0. It scores by **distinct moat types** present
    (data / network / integration / domain). Round 2 broadens each vocab to catch
    how moats are actually described in prose (data flywheel / 越用越准 / 独占接入 /
    领域 know-how), so real defensible ideas clear the floor, and adds a small
    *intensity* term (a candidate that talks about its data moat in several ways
    edges out one that mentions it once). Distinct-type breadth still dominates:
    two kinds of moat beats one. A bare idea sits near a small floor, not 0.1 flat.
    """
    text = c.text()
    vocabs = (_MOAT_DATA, _MOAT_NETWORK, _MOAT_INTEGRATION, _MOAT_DOMAIN)
    types_present = sum(1 for vocab in vocabs if _has_any(text, vocab))
    total_hits = sum(_count_hits(text, vocab) for vocab in vocabs)
    # Breadth (distinct types) is the primary driver; intensity (total mentions)
    # is a small tie-breaker so within-type richness still moves the score.
    breadth = _saturating(types_present, half=1.5)
    intensity = _saturating(total_hits, half=3.0)
    return round(0.1 + 0.78 * breadth + 0.12 * intensity, 4)


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
# NOTE(Round 2 严重度④):the six named factors below are a stable contract shared
# with idea_eval + studio — never deleted/renamed. ``payment_signal`` is a 7th,
# *additive* factor (round1 asked for paid demand as its own ranking input). Both
# idea_eval (iterates FACTORS) and studio (renders factors dynamically with a
# label fallback) absorb the new key without code changes.
FACTORS = {
    "market_freshness": market_freshness,
    "pain_intensity": pain_intensity,
    "build_cost": build_cost,
    "moat_signal": moat_signal,
    "competition_density": competition_density,
    "distribution_fit": distribution_fit,
    "payment_signal": payment_signal,
}

# Chinese display labels for the factor keys (keys stay English identifiers).
FACTOR_LABELS = {
    "market_freshness": "市场新鲜度",
    "pain_intensity": "痛点强度",
    "build_cost": "可落地性",
    "moat_signal": "护城河",
    "competition_density": "竞争稀缺度",
    "distribution_fit": "触达匹配度",
    "payment_signal": "付费信号",
}


def label(name: str) -> str:
    return FACTOR_LABELS.get(name, name)


def compute_factors(c: IdeaCandidate) -> dict[str, float]:
    """Run every factor over a candidate, rounding for stable serialization."""
    return {name: round(fn(c), 4) for name, fn in FACTORS.items()}
