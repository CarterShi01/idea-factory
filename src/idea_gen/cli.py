"""Command-line entry point. Thin by design: parse args, call the pipeline,
print a short summary. All real work lives in :mod:`idea_gen.pipeline`.
"""

from __future__ import annotations

import argparse
from datetime import date

from idea_core.llm import PendingHandoff, load_dotenv
from idea_core.models import SOURCE_BRAIN, SOURCE_EXTERNAL, SOURCE_PERSONA

from .pipeline import run_pipeline

_SOURCE_CHOICES = [SOURCE_EXTERNAL, SOURCE_BRAIN, SOURCE_PERSONA]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-gen",
        description="Turn three-source signals into ranked startup-idea candidates.",
    )
    parser.add_argument("--data-dir", default="data", help="input data directory (default: data)")
    parser.add_argument(
        "--output-dir", default="data/processed", help="where to write ideas.json / ideas.md"
    )
    parser.add_argument("--top-n", type=int, default=15, help="how many ideas in the daily report")
    parser.add_argument(
        "--date", default=None, help="reference date (ISO) for time-decay; default: today"
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=_SOURCE_CHOICES,
        default=None,
        help="subset of sources to use (default: all three)",
    )
    parser.add_argument(
        "--gen-backend",
        choices=["rule", "router", "cc", "mock"],
        default="rule",
        help="generation backend: rule (offline, default) / router (Tencent) / cc (manual handoff) / mock",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()

    try:
        result = run_pipeline(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            today=today,
            top_n=args.top_n,
            sources=args.sources,
            gen_backend=args.gen_backend,
        )
    except PendingHandoff as ph:
        return report_handoff(ph)

    print(
        f"collected {result.raw_count} raw → {result.signal_count} signals "
        f"→ {result.deduped_count} after dedup → {result.candidate_count} candidates"
    )
    print(f"wrote {result.json_path} and {result.markdown_path}")
    print(f"top {min(args.top_n, len(result.scored))} ideas:")
    for rank, s in enumerate(result.scored[: args.top_n], start=1):
        print(f"  {rank:>2}. [{s.alpha:.3f}] {s.candidate.title}")
    return 0


def report_handoff(ph: PendingHandoff) -> int:
    """Print instructions for the manual Claude Code (CC) handoff and pause."""
    response_path = ph.request_path.parent / ph.request_path.name.replace(
        ".request.jsonl", ".response.jsonl"
    )
    print("\n⏸  LLM step paused for a manual Claude Code session (Max pool — no programmatic CC).")
    print(f"   request pack: {ph.request_path}  ({ph.count} items)")
    print("   1) open Claude Code by hand in this repo")
    print(f"   2) process the whole batch, writing responses to {response_path}")
    print("   3) re-run this command to resume.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
