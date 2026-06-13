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

# Topics currently in a fresh / rising window.
_TRENDING = {
    "ai", "agent", "agents", "llm", "rag", "copilot", "automation", "gpt",
    "embedding", "vector", "multimodal", "voice", "local-first", "privacy",
    "mcp", "fine-tune", "self-hosted",
}
# Words that signal a real, sharp pain.
_PAIN = {
    "expensive", "costly", "manual", "manually", "tedious", "slow", "broken",
    "frustrat", "waste", "wasting", "hate", "painful", "hard", "difficult",
    "confusing", "unreliable", "clunky", "hours", "repetitive", "missing",
    "lack", "struggle", "annoying", "overwhelm", "error-prone",
}
# Words that imply a heavy, non-solo build.
_COMPLEXITY = {
    "marketplace", "hardware", "logistics", "enterprise", "compliance",
    "hipaa", "two-sided", "regulat", "blockchain", "on-premise", "fleet",
    "supply", "warehouse", "payroll",
}
# Hints of defensibility / moat.
_MOAT = {
    "proprietary", "workflow", "integration", "dataset", "niche", "community",
    "network", "vertical", "domain", "fine-tune", "data",
}
# Hints of a crowded, undifferentiated space.
_CROWDED = {
    "another", "clone", "generic", "chatbot", "todo", "to-do", "note",
    "url shortener", "crud", "wrapper",
}
# Users this particular founder (software, also investing) can actually reach.
_REACHABLE = {
    "developer", "developers", "indie", "founder", "founders", "investor",
    "investors", "engineer", "engineers", "software", "startup", "saas",
    "builder", "builders", "analyst", "technical",
}


def _count_hits(text: str, vocab: set[str]) -> int:
    return sum(1 for term in vocab if term in text)


# --- factors --------------------------------------------------------------

def market_freshness(c: IdeaCandidate) -> float:
    """Is the idea riding a currently-fresh topic? Higher = fresher."""
    hits = _count_hits(c.text(), _TRENDING)
    return min(1.0, 0.1 + hits / 2.0)


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


def compute_factors(c: IdeaCandidate) -> dict[str, float]:
    """Run every factor over a candidate, rounding for stable serialization."""
    return {name: round(fn(c), 4) for name, fn in FACTORS.items()}
