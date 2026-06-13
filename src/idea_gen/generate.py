"""Stage 4 -- generate idea candidates from signals (deliberately over-generate).

The MVP backend is **rule-based and offline**: it expands each signal into a few
solution-shaped variants using templates. This is intentionally dumb -- per the
research, generation should be high-volume and cheap; the quality gate lives
downstream in ``idea-evl``, not here.

The single public entry point :func:`generate` takes a ``backend`` callable so a
future LLM backend (Verbalized Sampling, etc.) can slot in without touching the
pipeline. The default backend keeps the offline contract.
"""

from __future__ import annotations

from typing import Callable

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
