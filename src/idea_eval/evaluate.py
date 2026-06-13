"""idea_eval evaluation core -- screen idea candidates with a kill-gate.

This is the evaluation half's job, per the research: not "find the genius idea"
but "say no efficiently", like an investor screening deal flow.

Two mechanisms, both stage-0 rule-based and offline:

1. **Multiplicative-floor kill gate.** A fatal flaw on any *critical* dimension
   (no real pain, or not solo-buildable) kills the idea outright, no matter how
   well it scores elsewhere. This is the ``idea-validation-agents`` lesson: a
   single fatal short-board should collapse the score, not be averaged away.
2. **Weighted rubric score (0-100)** for the survivors, plus a templated
   "riskiest assumption" and a cheap (≤2 week / ≤\\$100) RAT experiment so the
   output is a *decision*, not just a number.

The factor *definitions* come from ``idea_core`` -- evl never recomputes them
differently from gen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from idea_core.factors import FACTORS

PURSUE = "pursue"
REVIEW = "review"
KILL = "kill"

# Critical dimensions: a fatal flaw here is disqualifying on its own.
CRITICAL = ("pain_intensity", "build_cost")
DEFAULT_FLOOR = 0.25

# Verdict bands on the 0-100 rubric score (for ideas that pass the kill gate).
PURSUE_AT = 60.0
REVIEW_AT = 45.0

# evl's own rubric weights (same factor names as idea_core; evl owns its
# emphasis). Pain and solo-buildability carry the most weight.
RUBRIC_WEIGHTS = {
    "pain_intensity": 0.30,
    "build_cost": 0.20,
    "distribution_fit": 0.18,
    "market_freshness": 0.14,
    "competition_density": 0.10,
    "moat_signal": 0.08,
}

# Human-readable labels for the riskiest-assumption / experiment templates.
_ASSUMPTION = {
    "pain_intensity": "Assumes the pain is real and sharp — currently the weakest signal.",
    "build_cost": "Assumes a solo founder can actually ship this — build cost looks high.",
    "distribution_fit": "Assumes you can reach these users — distribution is the weak point.",
    "market_freshness": "Assumes the window is still open — the topic may not be fresh.",
    "competition_density": "Assumes room to differentiate — the space looks crowded.",
    "moat_signal": "Assumes you can build a moat — defensibility is unclear.",
}
_EXPERIMENT = {
    "pain_intensity": "Run 5 problem-interviews + post the pain in 3 communities; look for unprompted 'I'd pay for this'. (1 week, $0)",
    "build_cost": "Time-box a 2-day spike on the hardest technical piece; if it isn't solo-shippable, drop it. (2 days, $0)",
    "distribution_fit": "Reach 20 target users via your existing channels; measure reply/interest rate. (1 week, $0)",
    "market_freshness": "Check search/HN/GitHub trend over the last 90 days; confirm it's rising, not peaked. (half day, $0)",
    "competition_density": "Sign up for the top 3 competitors; document the one gap you'd exploit. (2 days, <$100)",
    "moat_signal": "Spec the one workflow or data asset that would lock users in; validate with 3 users. (3 days, $0)",
}


@dataclass
class Evaluation:
    idea_id: str
    title: str
    verdict: str
    eval_score: float           # 0-100
    killed_by: list[str] = field(default_factory=list)
    riskiest_assumption: str = ""
    cheap_experiment: str = ""
    risk_flags: list[str] = field(default_factory=list)
    confidence: str = "real"
    factors: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _rubric_score(factors: dict[str, float]) -> float:
    total = sum(RUBRIC_WEIGHTS.get(name, 0.0) * factors.get(name, 0.0) for name in FACTORS)
    return round(total * 100, 1)


def _riskiest_dimension(factors: dict[str, float]) -> str:
    # Lowest-scoring factor among the ones we have; deterministic tie-break by name.
    known = {n: factors.get(n, 0.0) for n in FACTORS}
    return min(sorted(known), key=lambda n: known[n])


def _risk_flags(idea: dict, factors: dict[str, float]) -> list[str]:
    flags: list[str] = []
    if idea.get("confidence") == "synthetic":
        flags.append("Based on simulated persona pain — needs ≥1 real corroborating signal.")
    if factors.get("competition_density", 1.0) < 0.5:
        flags.append("Crowded space — differentiation unclear.")
    if factors.get("moat_signal", 1.0) <= 0.1:
        flags.append("No obvious moat.")
    if factors.get("build_cost", 1.0) < 0.5:
        flags.append("Heavy build for a one-person company.")
    return flags


def evaluate_idea(idea: dict, floor: float = DEFAULT_FLOOR) -> Evaluation:
    """Evaluate one candidate dict (as produced by idea_gen's ideas.json)."""
    factors = idea.get("factors", {})
    killed_by = [dim for dim in CRITICAL if factors.get(dim, 1.0) < floor]
    score = _rubric_score(factors)

    if killed_by:
        verdict = KILL
        score = round(score * 0.3, 1)        # fatal flaw collapses the score
    elif score >= PURSUE_AT:
        verdict = PURSUE
    elif score >= REVIEW_AT:
        verdict = REVIEW
    else:
        verdict = KILL

    dim = _riskiest_dimension(factors)
    return Evaluation(
        idea_id=idea.get("id", ""),
        title=idea.get("title", ""),
        verdict=verdict,
        eval_score=score,
        killed_by=killed_by,
        riskiest_assumption=_ASSUMPTION.get(dim, ""),
        cheap_experiment=_EXPERIMENT.get(dim, ""),
        risk_flags=_risk_flags(idea, factors),
        confidence=idea.get("confidence", "real"),
        factors=factors,
    )


_VERDICT_ORDER = {PURSUE: 0, REVIEW: 1, KILL: 2}


def evaluate_all(ideas: list[dict], floor: float = DEFAULT_FLOOR) -> list[Evaluation]:
    evaluations = [evaluate_idea(i, floor=floor) for i in ideas]
    # Sort: pursue first, then review, then kill; within a band by score desc.
    evaluations.sort(key=lambda e: (_VERDICT_ORDER[e.verdict], -e.eval_score, e.idea_id))
    return evaluations
