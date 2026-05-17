# Idea Factory

Idea Factory is an information collection and idea generation project.

The early demo focuses on collecting product launch information, organizing it into structured records, and generating startup idea candidates for further review.

This project is designed to become a lightweight AI-agent-driven idea production pipeline over time.

## Running the demo pipeline

The first demo runs entirely offline from a small built-in sample of product launches. It exercises the full shape of the pipeline — collect → normalize → generate ideas → write output — so future modules can be swapped in one at a time.

Requirements: Python 3.10+.

```bash
# from the repository root
python -m venv .venv
source .venv/bin/activate
pip install -e .

# run the pipeline (writes JSON and Markdown to data/processed/ by default)
idea-factory

# or pick a single format / custom output directory
idea-factory --format md --output-dir data/processed
```

You can also invoke it without installing:

```bash
PYTHONPATH=src python -m idea_factory.cli
```

### Pipeline modules

- `idea_factory.sources` — collects raw product records (currently a hardcoded sample).
- `idea_factory.normalize` — coerces raw records into a uniform structured shape.
- `idea_factory.ideas` — generates startup idea candidates from normalized records.
- `idea_factory.output` — writes results to `ideas.json` and/or `ideas.md`.
- `idea_factory.cli` — wires the modules together behind the `idea-factory` command.
