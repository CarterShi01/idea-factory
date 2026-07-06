"""⑥diligence 的 LLM-as-judge(只看 gate 幸存者,token-thrifty;反谄媚)。"""

from __future__ import annotations

from idea_factory.contract.models import (
    KILL,
    PURSUE,
    REVIEW,
    Evaluation,
    sort_evaluations,
)
from idea_factory.runtime.llm import build_request, render_template

from .prompts import _critique_block, _log_trace_batch, _survivor_fields

# judge 自己的 5 维 rubric(非生成侧因子——评审半场的投资人式标尺)。
JUDGE_DIMS = ("pain_real", "solo_buildable", "reachable", "defensible", "timing")
# If top-level score and the avg of judge_scores * 100 disagree by more than this,
# the judge flagged itself as internally inconsistent.
SCORE_DISAGREEMENT_GAP = 25.0


def judge_survivors(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    llm,
    config: dict,
    trace_data_dir=None,
    trace_run_id: str | None = None,
) -> list[Evaluation]:
    """Run the LLM judge over the gate survivors only (Top-K, token-thrifty).

    The cheap rule kill-gate has already removed the obvious losers; the LLM only
    sees pursue/review candidates, where adversarial judgment actually pays off.
    It may downgrade a survivor to ``kill``. Mutates and re-sorts ``evaluations``.

    If ``critique.critique_survivors`` ran first and populated ``e.critique``, the
    judge user prompt injects it via the ``{critique}`` placeholder and the judge
    must fill ``respond_to_critique`` — forcing engagement with the strongest
    objection. May raise ``PendingHandoff`` (CC-handoff mode); let it propagate.
    """
    survivors = [e for e in evaluations if e.verdict in (PURSUE, REVIEW)]
    if not survivors:
        return evaluations

    template = config.get("user_template", "")
    requests = []
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        fields = _survivor_fields(e, idea)
        fields["critique"] = _critique_block(e)
        requests.append(build_request(e.idea_id, render_template(template, fields), config))

    responses_list = llm.complete(requests)
    responses = {r.id: r for r in responses_list}
    _log_trace_batch(trace_data_dir, trace_run_id, "diligence", requests, responses, config.get("step", "judge"))
    for e in survivors:
        r = responses.get(e.idea_id)
        if not (r and r.ok and r.data):
            continue
        d = r.data
        e.judged_by = "llm"
        if d.get("verdict") in (PURSUE, REVIEW, KILL):
            e.verdict = d["verdict"]
        if isinstance(d.get("score"), (int, float)):
            e.eval_score = round(float(d["score"]), 1)
        e.killer_objection = d.get("killer_objection", "") or e.killer_objection
        e.riskiest_assumption = d.get("riskiest_assumption", "") or e.riskiest_assumption
        e.cheap_experiment = d.get("cheap_experiment", "") or e.cheap_experiment
        e.judge_rebuttal = d.get("respond_to_critique", "") or e.judge_rebuttal
        conf = d.get("confidence", "")
        if conf in ("high", "medium", "low"):
            e.judge_confidence = conf
            # Anti-overconfidence: low-confidence pursue/kill is forced to review
            # so a borderline call always falls into the human-audit lane.
            if conf == "low" and e.verdict in (PURSUE, KILL):
                e.verdict = REVIEW
                e.confidence_demoted = True
        reasons = d.get("reasons")
        if isinstance(reasons, list):
            e.judge_reasons = [
                {
                    "claim": str(item.get("claim", "")),
                    "evidence_ids": [str(x) for x in (item.get("evidence_ids") or []) if x],
                }
                for item in reasons
                if isinstance(item, dict)
            ]
        sub = d.get("scores")
        if isinstance(sub, dict):
            e.judge_scores = {
                name: round(float(sub[name]), 3)
                for name in JUDGE_DIMS
                if isinstance(sub.get(name), (int, float))
            }
            # Self-consistency: top-level score vs avg of 5 sub-dims should agree.
            if len(e.judge_scores) == len(JUDGE_DIMS):
                avg100 = sum(e.judge_scores.values()) / len(JUDGE_DIMS) * 100
                if abs(avg100 - e.eval_score) > SCORE_DISAGREEMENT_GAP:
                    e.risk_flags.append(
                        f"评委自相矛盾：顶层 {e.eval_score:.0f} 分与五维平均 "
                        f"{avg100:.0f} 分差距过大。"
                    )

    return sort_evaluations(evaluations)
