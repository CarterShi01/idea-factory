"""idea-eval CLI. Thin: parse args, run the evaluation, print a short summary.

Subcommands (``idea-eval retro ...``, ``idea-eval stats ...``) are dispatched
by inspecting the first positional argument before the main evaluate parser
runs -- the default (no subcommand) path is byte-for-byte the pre-existing
``idea-eval [--input ...]`` usage, so nothing that already scripts this CLI
breaks.
"""

from __future__ import annotations

import argparse
from datetime import date

from idea_core.llm import PendingHandoff, get_backend, load_dotenv, load_step_config

from . import calibrate as calibrate_mod
from . import retro as retro_mod
from . import stats as stats_mod
from .evaluate import DEFAULT_FLOOR, DEFAULT_MAX_PURSUE_FRAC
from .pipeline import run_evaluation

_SUBCOMMANDS = ("retro", "stats", "calibrate")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-eval",
        description="Screen idea-gen candidates with a kill-gate + rubric into decision memos.",
    )
    parser.add_argument(
        "--input", default="data/processed/ideas.json", help="ideas.json produced by idea-gen"
    )
    parser.add_argument(
        "--output-dir", default="data/processed", help="where to write screened.json / decision_memos.md"
    )
    parser.add_argument("--top-n", type=int, default=20, help="how many survivors in the memo report")
    parser.add_argument(
        "--floor", type=float, default=DEFAULT_FLOOR, help="kill-gate floor for critical dimensions"
    )
    parser.add_argument("--date", default=None, help="reference date (ISO); default: today")
    parser.add_argument(
        "--judge-backend",
        choices=["none", "router", "cc", "mock", "dify"],
        default="none",
        help="LLM-as-judge over kill-gate survivors: none (rule-only, default) / router (Tencent) / cc / mock / dify (Dify workflow)",
    )
    parser.add_argument(
        "--no-critique",
        dest="critique",
        action="store_false",
        default=True,
        help="skip the devil's advocate pass before the judge (default: on when --judge-backend != none)",
    )
    parser.add_argument(
        "--no-version",
        dest="version",
        action="store_false",
        default=True,
        help="skip snapshotting this run into data/processed/versions/ (default: commit a version)",
    )
    parser.add_argument(
        "--require-evidence",
        action="store_true",
        default=False,
        help=(
            "opt-in evidence-gated diligence (docs/design/pipeline-v2-plan.md §5④⑤): "
            "run idea_eval.enrich, demote ungrounded pursue to review, cap the batch's "
            "pursue fraction, and log verdicts + funnel counts to <evidence-data-dir>/ledger/"
        ),
    )
    parser.add_argument(
        "--evidence-data-dir", default="data",
        help="root data dir for the evidence ledger (default: data)",
    )
    parser.add_argument(
        "--evidence-live", action="store_true", default=False,
        help="allow enrich's fetchers to hit the network (currently a stubbed no-op; needs founder approval to wire)",
    )
    parser.add_argument(
        "--max-pursue-frac", type=float, default=DEFAULT_MAX_PURSUE_FRAC,
        help="forced-distribution cap on the pursue fraction per batch (only with --require-evidence)",
    )
    parser.add_argument(
        "--persona-pressure-backend",
        choices=["none", "router", "cc", "mock", "dify"],
        default="none",
        help=(
            "opt-in §5⑥ sub-step: sample personas to argue 'why I wouldn't buy this' against the "
            "FINAL pursue survivors (advisory only, never changes verdict). none=off (default)."
        ),
    )
    return parser


def _build_retro_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-eval retro",
        description="Record a real-world smoke-test result (the only ground truth this system has).",
    )
    parser.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    parser.add_argument("--candidate", required=True, help="candidate/idea id being reported on")
    parser.add_argument("--metric", required=True, help="metric name (e.g. signups, preorders)")
    parser.add_argument("--actual", type=float, required=True, help="the real value observed")
    parser.add_argument("--target", type=float, default=None, help="what the verdict predicted")
    parser.add_argument("--horizon-days", type=int, default=None, help="prediction horizon in days")
    parser.add_argument("--first-revenue", type=float, default=None, help="first real revenue, if any")
    parser.add_argument("--lesson", default="", help="one-line takeaway for next time (zero-token, wins if given)")
    parser.add_argument(
        "--tested-at", default=None, help="ISO date the test was run; default: today"
    )
    parser.add_argument(
        "--llm-lesson-backend",
        choices=["none", "router", "cc", "mock", "dify"],
        default="none",
        help="when --lesson is empty, extract a one-line lesson via LLM from the prediction/actual gap + verdict context",
    )
    return parser


def _build_stats_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-eval stats",
        description="Read-only funnel/tier/prediction-error report computed from data/ledger/.",
    )
    parser.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    return parser


def _build_calibrate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-eval calibrate",
        description=(
            "Read-only: correlate generation-side factors with real-world outcome performance. "
            "Never writes to any config -- prints a suggestion for you to apply by hand."
        ),
    )
    parser.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    parser.add_argument(
        "--min-sample", type=int, default=calibrate_mod.DEFAULT_MIN_SAMPLE,
        help="minimum usable outcomes before a suggestion is given (default: 10)",
    )
    return parser


def _report_handoff(ph: PendingHandoff) -> int:
    response_path = ph.request_path.parent / ph.request_path.name.replace(
        ".request.jsonl", ".response.jsonl"
    )
    name = ph.request_path.name
    if name.startswith("critique-"):
        step = "Critique"
    elif name.startswith("retro-lesson-"):
        step = "Retro-lesson"
    else:
        step = "Judge"
    print(f"\n⏸  {step} step paused for a manual Claude Code session (Max pool — no programmatic CC).")
    print(f"   request pack: {ph.request_path}  ({ph.count} survivors)")
    print("   1) open Claude Code by hand in this repo")
    print(f"   2) {step.lower()} the whole batch, writing responses to {response_path}")
    print("   3) re-run this command to resume.")
    return 2


def _retro_llm_backend(name: str, candidate: str, tested_at: str):
    if name == "cc":
        return get_backend("cc", job_dir="data/llm_jobs", job_name=f"retro-lesson-{candidate}-{tested_at}")
    if name == "dify":
        return get_backend("dify", step="retro_lesson")
    return get_backend(name)


def _retro_main(argv: list[str]) -> int:
    args = _build_retro_parser().parse_args(argv)
    tested_at = args.tested_at or date.today().isoformat()

    llm = None
    if not args.lesson and args.llm_lesson_backend != "none":
        llm = _retro_llm_backend(args.llm_lesson_backend, args.candidate, tested_at)

    try:
        outcome = retro_mod.record_outcome(
            args.data_dir,
            candidate_id=args.candidate,
            tested_at=tested_at,
            metric=args.metric,
            actual_value=args.actual,
            target=args.target,
            horizon_days=args.horizon_days,
            first_revenue=args.first_revenue,
            lesson=args.lesson,
            llm=llm,
            llm_config=load_step_config("retro_lesson") if llm is not None else None,
        )
    except PendingHandoff as ph:
        return _report_handoff(ph)

    err = retro_mod.prediction_error(outcome.to_dict())
    print(f"recorded outcome for {args.candidate}: {args.metric}={args.actual} (tested {tested_at})")
    if err is not None:
        print(f"  prediction error: {err:+.1%} vs target {args.target}")
    if outcome.lesson:
        print(f"  lesson: {outcome.lesson}")
    return 0


def _stats_main(argv: list[str]) -> int:
    args = _build_stats_parser().parse_args(argv)
    print(stats_mod.format_report(stats_mod.funnel_report(args.data_dir)))
    return 0


def _calibrate_main(argv: list[str]) -> int:
    args = _build_calibrate_parser().parse_args(argv)
    report = calibrate_mod.suggest_weights(args.data_dir, min_sample=args.min_sample)
    print(calibrate_mod.format_calibration(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if argv and argv[0] in _SUBCOMMANDS:
        if argv[0] == "retro":
            return _retro_main(argv[1:])
        if argv[0] == "stats":
            return _stats_main(argv[1:])
        if argv[0] == "calibrate":
            return _calibrate_main(argv[1:])

    args = build_parser().parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()

    try:
        result = run_evaluation(
            input_path=args.input,
            output_dir=args.output_dir,
            today=today,
            floor=args.floor,
            top_n=args.top_n,
            judge_backend=args.judge_backend,
            critique=args.critique,
            version=args.version,
            require_evidence=args.require_evidence,
            evidence_data_dir=args.evidence_data_dir,
            evidence_live=args.evidence_live,
            max_pursue_frac=args.max_pursue_frac,
            persona_pressure_backend=args.persona_pressure_backend,
        )
    except PendingHandoff as ph:
        return _report_handoff(ph)

    print(
        f"evaluated {result.evaluated} → {result.pursue} pursue · "
        f"{result.review} review · {result.killed} killed"
    )
    print(f"wrote {result.json_path} and {result.memos_path}")
    if result.weekly_report_path:
        print(f"wrote {result.weekly_report_path}")
    if result.version_id:
        print(f"committed version {result.version_id} → {args.output_dir}/versions/{result.version_id}/")
    survivors = [e for e in result.evaluations if e.verdict in ("pursue", "review")]
    print(f"top {min(args.top_n, len(survivors))} worth a look:")
    for rank, e in enumerate(survivors[: args.top_n], start=1):
        print(f"  {rank:>2}. [{e.eval_score:>4.0f}] {e.verdict:<7} {e.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
