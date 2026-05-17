"""Command-line entry point for the Idea Factory demo pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .ideas import generate_ideas
from .normalize import normalize_products
from .output import write_json, write_markdown
from .sources import collect_products


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="idea-factory",
        description="Collect product signals and generate startup idea candidates.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory to write output files (default: data/processed).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "md", "both"),
        default="both",
        help="Output format(s) to write (default: both).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    raw = collect_products()
    products = normalize_products(raw)
    ideas = generate_ideas(products)

    output_dir: Path = args.output_dir
    written: list[Path] = []
    if args.format in ("json", "both"):
        written.append(write_json(output_dir / "ideas.json", products, ideas))
    if args.format in ("md", "both"):
        written.append(write_markdown(output_dir / "ideas.md", products, ideas))

    print(f"Collected {len(products)} product(s), generated {len(ideas)} idea(s).")
    for path in written:
        print(f"Wrote {path}")
