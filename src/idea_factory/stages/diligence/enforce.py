"""⑥diligence 的强制纪律(全部纯代码):引证校验、证据接地、强制分布。

裁决后的最终 pass:没有真实证据支撑的 PURSUE 不许成立;引不出证据的 KILL 不予
采信;一个批次不许被 PURSUE 淹没("高效说不"纪律)。
"""

from __future__ import annotations

import math

from idea_factory.contract.models import (
    KILL,
    PURSUE,
    REVIEW,
    Evaluation,
    sort_evaluations,
)

DEFAULT_MAX_PURSUE_FRAC = 0.5


def enforce_evidence_grounding(evaluations: list[Evaluation]) -> list[Evaluation]:
    """Demote a PURSUE verdict to REVIEW when the evidence gate isn't satisfied.

    Must run after ``enrich.apply_evidence`` (a candidate the caller never ran
    enrichment on has ``evidence_ready=False`` by default, so calling this
    without ``apply_evidence`` first would demote every survivor -- that's a
    caller error, not a supported mode).
    """
    for e in evaluations:
        if e.verdict == PURSUE and not e.evidence_ready:
            e.verdict = REVIEW
            e.evidence_demoted = True
            reason = "/".join(e.evidence_missing) or "证据不足"
            e.risk_flags.append(f"无真实证据支撑({reason})——先补证据,再判定可测,不能直接 pursue。")
    return sort_evaluations(evaluations)


def enforce_citation(evaluations: list[Evaluation]) -> list[Evaluation]:
    """Validate the judge's ``judge_reasons`` against the candidate's own evidence.

    Two things happen, both scoped to LLM-judged evaluations only (``judged_by
    == "llm"``) -- the deterministic rule kill-gate never looks at evidence at
    all, so it isn't second-guessed here:

    1. **Strip hallucinated citations.** An ``evidence_ids`` entry that doesn't
       match any id in ``e.evidence`` is dropped (the judge cited evidence that
       doesn't exist -- treat the claim as uncited, not as validated).
    2. **Demote an un-cited KILL.** If real evidence exists for a candidate but
       none of the judge's reasons actually cite any of it, a KILL verdict is
       not trustworthy on its own -- demote to REVIEW (mirrors
       :func:`enforce_evidence_grounding`'s treatment of an ungrounded PURSUE).

    Must run after ``apply_evidence`` and ``judge_survivors``.
    """
    for e in evaluations:
        valid_ids = {ev.get("id") for ev in e.evidence}
        cited_any = False
        cleaned: list[dict] = []
        for r in e.judge_reasons:
            ids = [i for i in r.get("evidence_ids", []) if i in valid_ids]
            if ids:
                cited_any = True
            cleaned.append({"claim": r.get("claim", ""), "evidence_ids": ids})
        e.judge_reasons = cleaned

        if e.judged_by == "llm" and e.verdict == KILL and e.evidence and not cited_any:
            e.verdict = REVIEW
            e.citation_demoted = True
            e.risk_flags.append("有真实证据但裁决理由未引用任何证据编号——淘汰不予采信,按需补证据复核处理。")
    return sort_evaluations(evaluations)


def enforce_forced_distribution(
    evaluations: list[Evaluation],
    max_pursue_frac: float = DEFAULT_MAX_PURSUE_FRAC,
) -> list[Evaluation]:
    """Cap the PURSUE fraction of a batch (kill+review >= 50% discipline).

    Excess PURSUE (beyond the cap, weakest-scoring first) is demoted to REVIEW
    with ``forced_downgrade=True``. KILL verdicts are never touched.
    """
    total = len(evaluations)
    if total == 0:
        return evaluations
    cap = math.floor(total * max_pursue_frac)
    pursue = [e for e in evaluations if e.verdict == PURSUE]
    if len(pursue) <= cap:
        return evaluations
    pursue_sorted = sorted(pursue, key=lambda e: (-e.eval_score, e.idea_id))
    for e in pursue_sorted[cap:]:
        e.verdict = REVIEW
        e.forced_downgrade = True
        e.risk_flags.append("批次内 pursue 占比超限——强制降级复核(高效说不纪律,不许整批都待验证)。")
    return sort_evaluations(evaluations)
