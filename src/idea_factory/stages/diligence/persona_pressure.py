"""idea_eval.persona_pressure -- Stage 6 optional sub-step: 人群压力测试.

Per ``docs/design/pipeline-v2-plan.md`` §5⑥ (可选子步骤, M4+): for a candidate
that already survived diligence as PURSUE (test_now-bound), sample a few
personas from the shared pool (:mod:`idea_core.personas`) and have each argue,
in first person, why *they specifically* wouldn't buy/use it. Purely advisory
-- this NEVER changes verdict/tier, it's a pre-mortem for the founder to read
alongside the verdict, not another kill-gate.

Cost discipline (CLAUDE.md's first principle): this only ever runs against the
smallest surviving set (PURSUE only), so it sits at the top of the per-idea
cost curve but the lowest volume -- a handful of calls per batch, not per
candidate.
"""

from __future__ import annotations

from idea_factory.runtime.llm import LLMBackend, build_request, render_template
from idea_factory.runtime.personas import load_persona_pool

from idea_factory.contract.models import PURSUE, Evaluation

DEFAULT_PERSONAS_PER_CANDIDATE = 2


def _persona_fields(idea: dict, persona: dict) -> dict:
    return {
        "title": idea.get("title", ""),
        "pain": idea.get("pain", ""),
        "solution": idea.get("solution", ""),
        "persona_name": persona.get("persona", "目标用户"),
        "persona_domain": persona.get("domain", ""),
    }


def _request_id(idea_id: str, idx: int) -> str:
    return f"pp-{idea_id}-{idx}"


def run_persona_pressure(
    evaluations: list[Evaluation],
    ideas_by_id: dict[str, dict],
    llm: LLMBackend,
    config: dict,
    persona_pool: list[dict] | None = None,
    personas_per_candidate: int = DEFAULT_PERSONAS_PER_CANDIDATE,
) -> list[Evaluation]:
    """Attach ``persona_objections`` to each PURSUE evaluation (mutates + returns).

    A deterministic first-``personas_per_candidate`` slice of the pool is used
    per candidate (simple and reproducible; matching personas to a candidate's
    target_user more precisely is a future refinement, not required for this
    sub-step to be useful). No-op when the pool is empty or there are no
    PURSUE survivors -- never raises, never touches verdicts.

    May raise ``idea_core.llm.PendingHandoff`` (CC-handoff mode); let it
    propagate like every other LLM step in this codebase.
    """
    pool = persona_pool if persona_pool is not None else load_persona_pool()
    survivors = [e for e in evaluations if e.verdict == PURSUE]
    if not pool or not survivors:
        return evaluations

    template = config.get("user_template", "")
    requests = []
    request_map: dict[str, tuple[Evaluation, dict]] = {}
    for e in survivors:
        idea = ideas_by_id.get(e.idea_id, {})
        for idx, persona in enumerate(pool[:personas_per_candidate]):
            rid = _request_id(e.idea_id, idx)
            user = render_template(template, _persona_fields(idea, persona))
            requests.append(build_request(rid, user, config))
            request_map[rid] = (e, persona)

    responses = {r.id: r for r in llm.complete(requests)}
    for rid, (e, persona) in request_map.items():
        r = responses.get(rid)
        if not (r and r.ok and r.data):
            continue
        objection = (r.data.get("objection") or "").strip()
        if objection:
            e.persona_objections.append({"persona": persona.get("persona", ""), "objection": objection})

    return evaluations
