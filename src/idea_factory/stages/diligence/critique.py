"""⑥diligence 的对抗式批判(devil's advocate,judge 之前的独立 LLM 步)。"""

from __future__ import annotations

from idea_factory.contract.models import PURSUE, REVIEW, Evaluation
from idea_factory.runtime.llm import build_request, render_template

from .prompts import _log_trace_batch, _survivor_fields


def critique_survivors(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    llm,
    config: dict,
    trace_data_dir=None,
    trace_run_id: str | None = None,
) -> list[Evaluation]:
    """Run an adversarial 'devil's advocate' pass over the gate survivors.

    Pure attack: lists 3-5 concrete objections + a killer_objection + a
    doomed_assumption, with no scoring or final verdict. Output is then fed into
    ``judge.judge_survivors`` so the judge has to engage with the strongest
    objections rather than rubber-stamp the generator's output
    (anti-self-enhancement).

    Mutates ``evaluations`` in place (no re-sort — verdicts unchanged here).
    May raise ``PendingHandoff`` (CC-handoff mode); let it propagate.
    """
    survivors = [e for e in evaluations if e.verdict in (PURSUE, REVIEW)]
    if not survivors:
        return evaluations

    template = config.get("user_template", "")
    requests = []
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        user = render_template(template, _survivor_fields(e, idea))
        requests.append(build_request(e.idea_id, user, config))

    responses_list = llm.complete(requests)
    responses = {r.id: r for r in responses_list}
    _log_trace_batch(trace_data_dir, trace_run_id, "critique", requests, responses, config.get("step", "critique"))
    for e in survivors:
        r = responses.get(e.idea_id)
        if not (r and r.ok and r.data):
            continue
        d = r.data
        objs = d.get("objections")
        if isinstance(objs, list):
            e.critique = [str(o) for o in objs if o]
        e.critique_killer = d.get("killer_objection", "") or e.critique_killer
        e.doomed_assumption = d.get("doomed_assumption", "") or e.doomed_assumption

    return evaluations
