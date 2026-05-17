"""Command-line entrypoint for the Idea Factory demo pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import _load_mock_ideas
from .generate import RANK_MAX, RANK_MIN
from .pipeline import run
from .ranks import DEFAULT_RANKS_PATH, InvalidRankError, set_override

DEFAULT_INPUT = Path("data/raw/sample_products.json")
DEFAULT_OUTPUT_DIR = Path("data/processed")


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
    return parser


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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "rank":
        return _run_rank(args)
    return _run_pipeline(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
