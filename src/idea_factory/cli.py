"""Command-line entrypoint for the Idea Factory demo pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import _load_mock_ideas
from .collect import (
    DEFAULT_COLLECTED_PATH,
    SECONDS_PER_DAY,
    collect_all,
    run_scheduled,
    save_collected,
)
from .generate import RANK_MAX, RANK_MIN
from .match import find_related_ideas, format_suggestion
from .pipeline import run
from .ranks import DEFAULT_RANKS_PATH, InvalidRankError, set_override

DEFAULT_INPUT = Path("data/raw/sample_products.json")
DEFAULT_OUTPUT_DIR = Path("data/processed")
DEFAULT_COLLECT_LIMIT = 10


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-factory",
        description="Run the mock product-to-idea generation pipeline.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to the products JSON file (default: {DEFAULT_INPUT}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write ideas.json and ideas.md (default: {DEFAULT_OUTPUT_DIR}).",
    )

    subparsers = parser.add_subparsers(dest="command")
    rank_parser = subparsers.add_parser(
        "rank",
        help="Set a rank override for an existing idea.",
        description=(
            f"Persist a rank override (an integer in [{RANK_MIN}, {RANK_MAX}]) "
            "for the idea with the given id."
        ),
    )
    rank_parser.add_argument("idea_id", help="The id of the idea to re-rank.")
    rank_parser.add_argument("rank", type=int, help=f"New rank in [{RANK_MIN}, {RANK_MAX}].")

    subparsers.add_parser(
        "hello",
        help="Print a greeting to verify the package is installed.",
        description="Print 'Hello from idea-factory!' to stdout and exit 0.",
    )

    collect_parser = subparsers.add_parser(
        "collect",
        help="Fetch external signals (Hacker News / Product Hunt / domestic RSS).",
        description=(
            "Fetch external product/market signals, save them as JSON, and flag "
            "which existing ideas each new signal may relate to. This makes real "
            "network calls and is separate from the offline demo pipeline."
        ),
    )
    collect_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_COLLECT_LIMIT,
        help=f"Max items to fetch per source (default: {DEFAULT_COLLECT_LIMIT}).",
    )
    collect_parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_COLLECTED_PATH,
        help=f"Where to write collected signals (default: {DEFAULT_COLLECTED_PATH}).",
    )
    collect_parser.add_argument(
        "--no-match",
        action="store_true",
        help="Skip matching collected signals against existing ideas.",
    )
    collect_parser.add_argument(
        "--schedule",
        action="store_true",
        help="Keep running on a fixed interval (default: once per day) instead of exiting.",
    )
    collect_parser.add_argument(
        "--interval-hours",
        type=float,
        default=24.0,
        help="Interval in hours between scheduled runs (with --schedule; default: 24).",
    )
    return parser


def hello() -> int:
    """Print the v0.1 greeting used to verify the package is installed."""
    print("Hello from idea-factory!")
    return 0


def _run_pipeline(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")

    outputs = run(args.input, args.output_dir)
    print("Idea Factory demo complete.")
    print(f"  JSON:     {outputs['json']}")
    print(f"  Markdown: {outputs['markdown']}")
    return 0


def _run_rank(args: argparse.Namespace) -> int:
    if args.rank < RANK_MIN or args.rank > RANK_MAX:
        print(
            f"error: rank must be an integer in [{RANK_MIN}, {RANK_MAX}], got {args.rank}",
            file=sys.stderr,
        )
        return 2

    try:
        ideas = _load_mock_ideas()
    except FileNotFoundError as exc:
        print(f"error: could not load ideas: {exc}", file=sys.stderr)
        return 1

    known_ids = {idea.get("id") for idea in ideas}
    if args.idea_id not in known_ids:
        print(f"error: unknown idea id: {args.idea_id}", file=sys.stderr)
        return 1

    try:
        set_override(args.idea_id, args.rank, DEFAULT_RANKS_PATH)
    except InvalidRankError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Updated {args.idea_id} to rank {args.rank}")
    return 0


def _collect_once(args: argparse.Namespace) -> int:
    records = collect_all(hn_limit=args.limit, ph_limit=args.limit, feed_limit=args.limit)
    out_path = save_collected(records, args.output)
    print(f"Collected {len(records)} signal(s) -> {out_path}")

    if args.no_match or not records:
        return len(records)

    try:
        ideas = _load_mock_ideas()
    except FileNotFoundError as exc:
        print(f"warning: could not load ideas for matching: {exc}", file=sys.stderr)
        return len(records)

    matches = find_related_ideas(records, ideas)
    if not matches:
        print("No new signals appear related to your existing ideas.")
    else:
        print(f"{len(matches)} possible idea connection(s):")
        for match in matches:
            print(f"  - {format_suggestion(match)}")
    return len(records)


def _run_collect(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("error: --limit must be a positive integer", file=sys.stderr)
        return 2

    if not args.schedule:
        _collect_once(args)
        return 0

    interval_seconds = int(args.interval_hours * 3600) if args.interval_hours > 0 else SECONDS_PER_DAY
    print(f"Scheduled collection every {args.interval_hours}h. Press Ctrl+C to stop.")
    try:
        run_scheduled(lambda: _collect_once(args), interval_seconds=interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "rank":
        return _run_rank(args)
    if args.command == "hello":
        return hello()
    if args.command == "collect":
        return _run_collect(args)
    return _run_pipeline(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
