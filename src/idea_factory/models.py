"""Data model for the Idea Factory pipeline.

Two record shapes flow through the pipeline:

* :class:`Signal`   -- a normalized, structured input record from one of the
  three sources (external event / brain inbox / simulated pain). This is the
  "signal" in the quant analogy: a time-stamped, low-signal-to-noise event.
* :class:`IdeaCandidate` -- a generated startup-idea candidate derived from a
  signal.
* :class:`ScoredCandidate` -- an idea candidate plus its factor scores and the
  combined ``alpha`` (ranking score).

All factor definitions live in :mod:`idea_factory.factors`; keeping the data
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

    def text(self) -> str:
        """Concatenated lowercase text, used by factors and dedup."""
        parts = [self.title, self.pain, self.solution, self.target_user, self.category or ""]
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
