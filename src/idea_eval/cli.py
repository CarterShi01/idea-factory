"""idea-eval CLI. Thin: parse args, run the evaluation, print a short summary."""

from __future__ import annotations

import argparse
from datetime import date

from idea_core.llm import PendingHandoff, load_dotenv

from .evaluate import DEFAULT_FLOOR
from .pipeline import run_evaluation


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
        choices=["none", "router", "cc", "mock"],
        default="none",
        help="LLM-as-judge over kill-gate survivors: none (rule-only, default) / router (Tencent) / cc / mock",
    )
    parser.add_argument(
        "--no-critique",
        dest="critique",
        action="store_false",
        default=True,
        help="skip the devil's advocate pass before the judge (default: on when --judge-backend != none)",
    )
    return parser


def _report_handoff(ph: PendingHandoff) -> int:
    response_path = ph.request_path.parent / ph.request_path.name.replace(
        ".request.jsonl", ".response.jsonl"
    )
    step = "Critique" if ph.request_path.name.startswith("critique-") else "Judge"
    print(f"\n⏸  {step} step paused for a manual Claude Code session (Max pool — no programmatic CC).")
    print(f"   request pack: {ph.request_path}  ({ph.count} survivors)")
    print("   1) open Claude Code by hand in this repo")
    print(f"   2) {step.lower()} the whole batch, writing responses to {response_path}")
    print("   3) re-run this command to resume.")
    return 2


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
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
        )
    except PendingHandoff as ph:
        return _report_handoff(ph)

    print(
        f"evaluated {result.evaluated} → {result.pursue} pursue · "
        f"{result.review} review · {result.killed} killed"
    )
    print(f"wrote {result.json_path} and {result.memos_path}")
    survivors = [e for e in result.evaluations if e.verdict in ("pursue", "review")]
    print(f"top {min(args.top_n, len(survivors))} worth a look:")
    for rank, e in enumerate(survivors[: args.top_n], start=1):
        print(f"  {rank:>2}. [{e.eval_score:>4.0f}] {e.verdict:<7} {e.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
