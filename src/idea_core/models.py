"""Data model for the Idea Factory pipeline.

Two record shapes flow through the pipeline:

* :class:`Signal`   -- a normalized, structured input record from one of the
  three sources (external event / brain inbox / simulated pain). This is the
  "signal" in the quant analogy: a time-stamped, low-signal-to-noise event.
* :class:`IdeaCandidate` -- a generated startup-idea candidate derived from a
  signal.
* :class:`ScoredCandidate` -- an idea candidate plus its factor scores and the
  combined ``alpha`` (ranking score).

All factor definitions live in :mod:`idea_core.factors`; keeping the data
model dumb (no business logic) is deliberate so the same definitions can be
shared with the downstream ``idea-evl`` repo without logic drift.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# The three idea sources. Kept as plain strings so records serialize cleanly.
SOURCE_EXTERNAL = "external_event"   # outside-world signal: launches, trends, papers
SOURCE_BRAIN = "brain_inbox"         # ideas the founder jotted down
SOURCE_PERSONA = "pain_persona"      # simulated target-user pain analysis


def bucket_of(source: str) -> str:
    """漏斗粗排/打散的来源桶(共享契约,两半都用):英文 HN 市场机会 vs 中文(人群/灵感/独占)。
    住 idea_core 而非 idea_gen —— 两半只依赖 idea_core、绝不互相依赖(隔离铁律)。"""
    return "en" if source == SOURCE_EXTERNAL else "zh"

CONFIDENCE_REAL = "real"
CONFIDENCE_SYNTHETIC = "synthetic"   # persona-simulated, treat with suspicion


@dataclass
class Signal:
    """A normalized input signal (output of the normalize stage)."""

    id: str                       # stable id, see normalize._stable_id
    source: str                   # one of SOURCE_*
    source_name: str              # concrete origin: hn / github / manual / persona...
    title: str
    raw_text: str
    observed_on: str              # ISO date the event happened / idea was captured
    pain_statement: str = ""      # abstracted "who struggles with what" (normalize)
    dedup_key: str = ""           # lexical key used by the dedup stage
    url: str | None = None
    category: str | None = None
    confidence: str = CONFIDENCE_REAL
    topic: str = ""               # 趋势检测的话题 key（normalize 设；通常=category）
    trend_status: str = "steady"  # rising / steady / peaked（动态模式由 trends 回填）
    growth_speed: float = 0.0     # 0-1，话题上升速度（动态模式）
    target_user: str = ""         # 源③人群标签等自带的目标用户（normalize 透传；生成阶段优先用它，避免 dev 默认值覆盖）
    money_trace: str = ""         # pipeline-v2 §5①:谁在为此付费/雇人/成交的痕迹描述（招聘/成交/评论类源自带，其余源留空）

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IdeaCandidate:
    """A generated idea candidate (output of the generate stage)."""

    id: str
    signal_id: str
    source: str
    title: str
    pain: str
    solution: str
    target_user: str
    observed_on: str
    confidence: str = CONFIDENCE_REAL
    category: str | None = None
    trend_status: str = "steady"  # 从来源 Signal 透传，供 market_freshness 因子使用
    growth_speed: float = 0.0
    # Round-1 真方案三要素（投资人评审严重度①⑤：模板填空 + mode collapse）。
    # 新增字段、向后兼容：旧 ideas.json 缺这几个键时反序列化用默认空值即可。
    mechanism: str = ""    # 具体技术/产品实现路径，不能只说 "AI/LLM 智能体"
    why_now: str = ""      # 为什么现有方案解决不了 / 为什么是现在的机会窗口
    mvp_week1: str = ""    # 第 1 周 MVP 能交付的最小可用功能
    # ff1 founder-fit 迭代①（投资人评审 ff1：流水线产通用货、2/10）：monopoly 三问。
    # 强制每条候选回答『为什么只有他能做成 / 怎么零成本拿前 10 客户 / YC 毕业生抄了为何失败』，
    # 让 founder-monopoly 思考落进结构化字段（既给生成侧约束，也给评估侧/人审材料）。
    # 新增字段、向后兼容：旧 ideas.json 缺这几个键时反序列化用默认空值即可。
    why_only_me: str = ""        # 为什么只有这位创始人能做成（杠杆其独占优势）
    first_10_customers: str = "" # 怎么零成本拿到前 10 个付费客户（具体到他的渠道/人群）
    copy_fails_because: str = "" # 通用 YC 毕业生抄了这个 idea 为什么会失败
    # Round 3（三源融合护城河，投资人复评 #2 + mission）：当一条候选由**多个不同
    # 来源**的信号汇聚而成（external_event + brain_inbox + pain_persona 指向同一
    # 主题），记录参与融合的来源类型列表。普通（单源）候选留空 []。新增字段、向后
    # 兼容：旧 ideas.json 缺此键时反序列化用默认空列表。
    fusion_sources: list[str] = field(default_factory=list)

    def text(self) -> str:
        """Concatenated lowercase text, used by factors and dedup."""
        parts = [
            self.title,
            self.pain,
            self.solution,
            self.target_user,
            self.mechanism,
            self.why_now,   # Round 2: why_now carries moat/timing/paid-demand evidence
            # ff1 founder-fit: the monopoly fields carry the founder-edge / channel /
            # language-region language the moat & distribution factors key on.
            self.why_only_me,
            self.first_10_customers,
            self.copy_fails_because,
            self.category or "",
        ]
        return " ".join(p for p in parts if p).lower()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoredCandidate:
    """An idea candidate plus its factor scores and combined alpha."""

    candidate: IdeaCandidate
    factors: dict[str, float] = field(default_factory=dict)
    alpha: float = 0.0            # final ranking score after time decay
    decay: float = 1.0            # the time-decay multiplier that was applied

    def to_dict(self) -> dict:
        d = self.candidate.to_dict()
        d["factors"] = self.factors
        d["alpha"] = self.alpha
        d["decay"] = self.decay
        return d


# --- pipeline-v2 additions (docs/design/pipeline-v2-plan.md §4) ------------
#
# Evidence / Outcome are new, additive record types for the enrich and retro
# stages. They deliberately do NOT touch Signal / IdeaCandidate / ScoredCandidate
# above -- those remain the contract idea_gen <-> idea_eval already share, and
# every existing consumer (Studio, tests, dify flows) keeps working unchanged.

# Evidence kinds (idea_eval.enrich's evidence gate checks for these).
EVIDENCE_PAYING_PROOF = "paying_proof"
EVIDENCE_COMPETITOR_PRICING = "competitor_pricing"
EVIDENCE_REACH_PATH = "reach_path"
EVIDENCE_HIRING = "hiring"
EVIDENCE_DEAL = "deal"


@dataclass
class Evidence:
    """One structured, sourced piece of real-world evidence for a candidate.

    Produced by :mod:`idea_eval.enrich` (fixture-backed by default; a live
    fetcher is an explicit, founder-approved follow-up per CLAUDE.md's "no real
    external API calls without approval" rule). ``valid`` is False when
    ``source_date`` is more than 24 months old (cheat-on-money's staleness
    rule) -- stale evidence doesn't count toward the evidence gate.
    """

    id: str
    candidate_id: str
    kind: str                      # one of EVIDENCE_* above
    source_url: str
    source_date: str = ""          # ISO date the evidence itself is from
    fetched_at: str = ""
    summary: str = ""
    numbers: dict = field(default_factory=dict)   # e.g. {"price": 29, "currency": "USD"}
    valid: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        known = {
            k: d[k] for k in (
                "id", "candidate_id", "kind", "source_url", "source_date",
                "fetched_at", "summary", "numbers", "valid",
            ) if k in d
        }
        return cls(**known)


@dataclass
class Outcome:
    """A founder-recorded real-world smoke-test result (retro's ground truth).

    Mirrors :class:`idea_core.ledger.Outcome` (kept here too so idea_eval code
    can type against ``idea_core.models.Outcome`` without importing ``ledger``
    just for the type -- both serialize to the identical dict shape).
    """

    candidate_id: str
    tested_at: str
    prediction: dict = field(default_factory=dict)
    actual: dict = field(default_factory=dict)
    first_revenue: float | None = None
    lesson: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Outcome":
        known = {
            k: d[k] for k in (
                "candidate_id", "tested_at", "prediction", "actual",
                "first_revenue", "lesson",
            ) if k in d
        }
        return cls(**known)
