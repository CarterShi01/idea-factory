"""idea_eval.retro -- Stage 8: record real-world smoke-test results.

Per ``docs/design/pipeline-v2-plan.md`` §5⑧: this is the only ground truth the
system has. Every other stage's weights/prompts are a prior; ``outcomes.jsonl``
is the only place reality talks back. Deliberately zero-token / zero-network,
mirroring this codebase's "cheap by default" convention: the founder types the
actual number and (optionally) a one-line lesson; an LLM-assisted lesson
extraction from the full prediction-vs-actual trace is a natural follow-up but
not required for the loop to be useful.
"""

from __future__ import annotations

from pathlib import Path

from idea_core import ledger
from idea_core.models import Outcome


def record_outcome(
    data_dir: str | Path,
    candidate_id: str,
    tested_at: str,
    metric: str,
    actual_value: float,
    target: float | None = None,
    horizon_days: int | None = None,
    first_revenue: float | None = None,
    lesson: str = "",
) -> Outcome:
    """Record one smoke-test result and append it to ``outcomes.jsonl``."""
    prediction: dict = {"metric": metric}
    if target is not None:
        prediction["target"] = target
    if horizon_days is not None:
        prediction["horizon_days"] = horizon_days

    outcome = Outcome(
        candidate_id=candidate_id,
        tested_at=tested_at,
        prediction=prediction,
        actual={"metric": metric, "value": actual_value},
        first_revenue=first_revenue,
        lesson=lesson,
    )
    ledger.log_outcome(data_dir, outcome)
    return outcome


def prediction_error(outcome: dict) -> float | None:
    """Signed relative error ``(actual - target) / target``; ``None`` if no target."""
    pred = outcome.get("prediction") or {}
    actual = outcome.get("actual") or {}
    target = pred.get("target")
    value = actual.get("value")
    if not isinstance(target, (int, float)) or target == 0 or not isinstance(value, (int, float)):
        return None
    return round((value - target) / target, 4)


def summarize_outcomes(data_dir: str | Path) -> dict:
    """Aggregate all recorded outcomes -- feeds ``idea-eval stats``."""
    outcomes = ledger.read_outcomes(data_dir)
    errors = [e for e in (prediction_error(o) for o in outcomes) if e is not None]
    revenue_events = [o for o in outcomes if o.get("first_revenue")]
    return {
        "count": len(outcomes),
        "avg_prediction_error": round(sum(errors) / len(errors), 4) if errors else None,
        "first_revenue_events": len(revenue_events),
        "lessons": [o.get("lesson") for o in outcomes if o.get("lesson")],
    }
