"""Command-line entry point. Thin by design: parse args, call the pipeline,
print a short summary. All real work lives in :mod:`idea_gen.pipeline`.
"""

from __future__ import annotations

import argparse
from datetime import date

from idea_core.models import SOURCE_BRAIN, SOURCE_EXTERNAL, SOURCE_PERSONA
from .pipeline import run_pipeline

_SOURCE_CHOICES = [SOURCE_EXTERNAL, SOURCE_BRAIN, SOURCE_PERSONA]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-factory",
        description="Offline MVP: turn three-source signals into ranked startup-idea candidates.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()

    result = run_pipeline(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        today=today,
        top_n=args.top_n,
        sources=args.sources,
    )

    print(
        f"collected {result.raw_count} raw → {result.signal_count} signals "
        f"→ {result.deduped_count} after dedup → {result.candidate_count} candidates"
    )
    print(f"wrote {result.json_path} and {result.markdown_path}")
    print(f"top {min(args.top_n, len(result.scored))} ideas:")
    for rank, s in enumerate(result.scored[: args.top_n], start=1):
        print(f"  {rank:>2}. [{s.alpha:.3f}] {s.candidate.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
