"""Command-line entrypoint for the Idea Factory demo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-factory",
        description="Run the Idea Factory demo pipeline.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="md",
        help="Output format for generated ideas (default: md).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write output to this file instead of stdout.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of source items processed.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    result = pipeline.run(limit=args.limit)
    rendered = pipeline.render_ideas(result.ideas, args.format)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {len(result.ideas)} idea(s) to {args.output}")
    else:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
