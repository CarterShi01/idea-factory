"""idea_eval.retro -- Stage 8: record real-world smoke-test results.

Per ``docs/design/pipeline-v2-plan.md`` §5⑧: this is the only ground truth the
system has. Every other stage's weights/prompts are a prior; ``outcomes.jsonl``
is the only place reality talks back. Zero-token by default, mirroring this
codebase's "cheap by default" convention: the founder types the actual number
and (optionally) a one-line lesson. :func:`extract_lesson_llm` is the opt-in
LLM-assisted path -- given a founder-typed ``lesson`` is empty, it can turn the
prediction-vs-actual gap (plus the candidate's own verdict context, read back
from ``verdicts.jsonl``) into a one-line takeaway.
"""

from __future__ import annotations

from pathlib import Path

from idea_core import ledger
from idea_core.llm import LLMBackend, build_request, render_template
from idea_core.models import Outcome


def latest_verdict_for(data_dir: str | Path, candidate_id: str) -> dict:
    """Most recently logged verdict for ``candidate_id`` (verdicts.jsonl uses the
    key ``idea_id``, same entity as an outcome's ``candidate_id``). ``{}`` if none
    was ever logged (e.g. ``require_evidence`` never ran) -- lesson extraction
    still works, just without verdict context.
    """
    records = ledger.read_jsonl(ledger.ledger_dir(data_dir) / ledger.VERDICTS)
    matches = [r for r in records if r.get("idea_id") == candidate_id]
    return matches[-1] if matches else {}


def _lesson_fields(candidate_id, metric, target, actual_value, horizon_days, verdict: dict) -> dict:
    return {
        "candidate_id": candidate_id,
        "title": verdict.get("title", ""),
        "verdict_tier": verdict.get("verdict", ""),
        "riskiest_assumption": verdict.get("riskiest_assumption", ""),
        "smoke_test_metric": metric,
        "target": "" if target is None else str(target),
        "actual": str(actual_value),
        "horizon_days": "" if horizon_days is None else str(horizon_days),
    }


def extract_lesson_llm(
    candidate_id: str,
    metric: str,
    target: float | None,
    actual_value: float,
    horizon_days: int | None,
    verdict: dict,
    llm: LLMBackend,
    config: dict,
) -> str:
    """One-shot LLM call: prediction vs actual + verdict context -> one-line lesson.

    Best-effort: a failed/malformed response yields ``""`` (caller falls back to
    no lesson, never raises -- a retro record should never be blocked by an LLM
    hiccup). May raise ``idea_core.llm.PendingHandoff`` in CC-handoff mode, same
    as every other LLM step in this codebase; let it propagate.
    """
    fields = _lesson_fields(candidate_id, metric, target, actual_value, horizon_days, verdict)
    template = config.get("user_template", "")
    req = build_request(f"retro-{candidate_id}", render_template(template, fields), config)
    responses = llm.complete([req])
    if responses and responses[0].ok and responses[0].data:
        return (responses[0].data.get("lesson") or "").strip()
    return ""


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
    llm: LLMBackend | None = None,
    llm_config: dict | None = None,
) -> Outcome:
    """Record one smoke-test result and append it to ``outcomes.jsonl``.

    ``lesson`` (founder-typed, zero-token) wins if given. When it's empty AND
    ``llm`` is provided, :func:`extract_lesson_llm` fills it in from the
    candidate's own verdict context (read from ``verdicts.jsonl``) -- opt-in,
    default path is unchanged.
    """
    if not lesson and llm is not None:
        verdict = latest_verdict_for(data_dir, candidate_id)
        lesson = extract_lesson_llm(
            candidate_id, metric, target, actual_value, horizon_days, verdict,
            llm, llm_config or {},
        )

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
