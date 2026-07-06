"""⑥diligence 消费 enrich 工件的接线:把证据 + 证据门结果挂到 Evaluation 上。"""

from __future__ import annotations

from idea_factory.contract.models import Evaluation


def apply_evidence(
    evaluations: list[Evaluation],
    evidence_by_id: dict[str, list],
    gate_by_id: dict[str, tuple[bool, list[str]]],
) -> list[Evaluation]:
    """Attach each evaluation's fetched evidence + gate result (mutates in place).

    ``evidence_by_id`` values may be :class:`idea_factory.contract.models.Evidence`
    objects or plain dicts (both accepted so callers can pass enrich 工件's
    output directly).
    """
    for e in evaluations:
        evs = evidence_by_id.get(e.idea_id, [])
        e.evidence = [ev.to_dict() if hasattr(ev, "to_dict") else ev for ev in evs]
        ready, missing = gate_by_id.get(e.idea_id, (False, []))
        e.evidence_ready = ready
        e.evidence_missing = list(missing)
    return evaluations
