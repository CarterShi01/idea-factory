"""Stage 4 -- generate idea candidates from signals (deliberately over-generate).

Two backends, same output type:

* :func:`generate` -- the offline **rule-based** default. Expands each signal into
  a few solution-shaped variants. Dumb on purpose: generation should be cheap and
  high-volume; the quality gate is downstream in ``idea_eval``.
* :func:`generate_llm` -- the **LLM (A) backend**. Renders one batched request per
  signal from ``config/llm/generate.json`` and runs it through any
  :class:`idea_core.llm.LLMBackend` (Tencent router / CC-handoff / mock). The
  batch-first contract means one ``complete()`` call covers all signals.

Both keep the same contract so the pipeline can switch between them with a flag.
"""

from __future__ import annotations

from typing import Callable

from idea_core.llm import LLMBackend, build_request, render_template
from idea_core.models import IdeaCandidate, Signal

# Each template turns a pain into a differently-angled solution. Keeping a small
# fixed set makes generation deterministic and reproducible for the demo.
_SOLUTION_TEMPLATES: list[tuple[str, str]] = [
    ("tool", "A focused tool that removes the manual work behind: {pain}"),
    ("agent", "An LLM agent that monitors and acts on: {pain}"),
    ("service", "A done-for-you service that resolves: {pain}"),
]

_DEFAULT_USER = "Software builders and indie founders"


def _target_user(signal: Signal) -> str:
    cat = (signal.category or "").lower()
    if "dev" in cat or "ai" in cat or "software" in cat:
        return "Developers and technical founders"
    if "invest" in cat or "finance" in cat:
        return "Solo investors tracking deal flow"
    if "market" in cat or "content" in cat:
        return "Indie marketers and creators"
    return _DEFAULT_USER


def _rule_based_backend(signal: Signal) -> list[IdeaCandidate]:
    pain = signal.pain_statement or signal.title
    if not pain:
        return []
    user = _target_user(signal)
    candidates: list[IdeaCandidate] = []
    for idx, (angle, template) in enumerate(_SOLUTION_TEMPLATES):
        candidates.append(
            IdeaCandidate(
                id=f"{signal.id}-{idx}",
                signal_id=signal.id,
                source=signal.source,
                title=f"{angle.title()} for: {signal.title}"[:120],
                pain=pain,
                solution=template.format(pain=pain),
                target_user=user,
                observed_on=signal.observed_on,
                confidence=signal.confidence,
                category=signal.category,
            )
        )
    return candidates


Backend = Callable[[Signal], list[IdeaCandidate]]


def generate(signals: list[Signal], backend: Backend = _rule_based_backend) -> list[IdeaCandidate]:
    candidates: list[IdeaCandidate] = []
    for signal in signals:
        candidates.extend(backend(signal))
    return candidates


# --- A: LLM generation backend -------------------------------------------


def _signal_fields(signal: Signal) -> dict:
    return {
        "title": signal.title,
        "pain_statement": signal.pain_statement,
        "category": signal.category or "",
        "source": signal.source,
        "observed_on": signal.observed_on,
    }


def _first(item: dict, *keys: str) -> str:
    for k in keys:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _candidates_from_response(signal: Signal, data: dict | None) -> list[IdeaCandidate]:
    if not data:
        return []
    # Prefer the requested {"candidates": [...]} shape, but tolerate a model that
    # returns a single idea object or a differently-keyed list.
    items = data.get("candidates")
    if not isinstance(items, list):
        items = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(items, list):
        items = [data] if any(k in data for k in ("title", "idea", "idea_name", "name")) else []

    out: list[IdeaCandidate] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = _first(item, "title", "idea_name", "name", "idea")
        if not title:
            continue
        out.append(
            IdeaCandidate(
                id=f"{signal.id}-{idx}",
                signal_id=signal.id,
                source=signal.source,
                title=title[:120],
                pain=_first(item, "pain", "problem", "pain_point") or signal.pain_statement,
                solution=_first(item, "solution", "description", "one_sentence_description"),
                target_user=_first(item, "target_user", "user", "audience") or _DEFAULT_USER,
                observed_on=signal.observed_on,
                confidence=signal.confidence,
                category=signal.category,
            )
        )
    return out


def generate_llm(signals: list[Signal], llm: LLMBackend, config: dict) -> list[IdeaCandidate]:
    """LLM (A) backend: one batched request per signal, a single complete() call.

    May raise ``idea_core.llm.PendingHandoff`` when the backend is CC-handoff and
    the response pack isn't ready yet -- callers should let it propagate to the CLI.
    """
    template = config.get("user_template", "")
    requests = [
        build_request(s.id, render_template(template, _signal_fields(s)), config)
        for s in signals
    ]
    responses = llm.complete(requests)
    by_id = {r.id: r for r in responses}

    candidates: list[IdeaCandidate] = []
    for s in signals:
        r = by_id.get(s.id)
        if r and r.ok:
            candidates.extend(_candidates_from_response(s, r.data))
    return candidates
