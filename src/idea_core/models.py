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
