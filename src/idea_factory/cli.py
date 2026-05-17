"""Command-line entrypoint for the Idea Factory demo pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")

    outputs = run(args.input, args.output_dir)
    print("Idea Factory demo complete.")
    print(f"  JSON:     {outputs['json']}")
    print(f"  Markdown: {outputs['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
