"""idea_eval -- the evaluation + kill-gate half of the Idea Factory system.

Reads idea_gen's ranked candidates (``data/processed/ideas.json``), screens them
with a multiplicative-floor kill gate plus a weighted rubric, and writes the
survivors as decision memos (verdict + riskiest assumption + a cheap RAT test).

Its first job is to *say no efficiently*. Shares the data model and factor
library with ``idea_gen`` via ``idea_core``; it never imports ``idea_gen``.
"""

from .evaluate import KILL, PURSUE, REVIEW, Evaluation, evaluate_all, evaluate_idea
from .pipeline import EvalResult, run_evaluation

__version__ = "0.1.0"
__all__ = [
    "run_evaluation",
    "EvalResult",
    "evaluate_idea",
    "evaluate_all",
    "Evaluation",
    "PURSUE",
    "REVIEW",
    "KILL",
    "__version__",
]
