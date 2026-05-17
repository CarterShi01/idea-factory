# Idea Factory

Idea Factory is an information collection and idea generation project.

The early demo focuses on collecting product launch information, organizing it into structured records, and generating startup idea candidates for further review.

This project is designed to become a lightweight AI-agent-driven idea production pipeline over time.

## Demo pipeline

The first demo wires up four placeholder stages so the end-to-end shape is in place before any real sources or models are added:

1. **`sources`** — return raw items from public launch feeds. The demo ships a small in-memory sample.
2. **`normalize`** — convert each raw item into a uniform `Product` record.
3. **`ideate`** — riff on each product to produce a candidate startup idea.
4. **`render`** — emit the candidates as JSON or Markdown.

`pipeline.run()` chains the four stages; `idea_factory.cli` is the user-facing entry point.

## Run the demo

Requires Python 3.10+.

```bash
# from the repo root
pip install -e .

# print Markdown to stdout
idea-factory

# write JSON to a file
idea-factory --format json --output data/processed/ideas.json

# limit how many source items are processed
idea-factory --limit 2
```

Without installing, you can run the module directly:

```bash
PYTHONPATH=src python -m idea_factory.cli --format md
```

## Project layout

```
src/idea_factory/
  cli.py         # argparse entry point
  pipeline.py    # orchestrates the four stages
  sources.py     # placeholder source collector
  normalize.py   # raw item -> Product
  ideate.py      # Product -> Idea
  render.py      # Idea -> JSON / Markdown
```

See `docs/project-brief.md` for the broader scope and non-goals.
