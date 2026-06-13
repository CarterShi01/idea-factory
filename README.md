# Idea Factory

Turns **three sources of signal** — external events, the founder's own ideas, and
simulated target-user pain — into a ranked daily list of startup-idea candidates.

This repo is the **generation + factor-scoring** half of the system (the "alpha"
side, in the quant analogy). The **evaluation / kill-gate** half lives in the
sibling `idea-evl` repo. The design rationale, the open-source landscape it
borrows from, and the full roadmap are in [`docs/research/`](docs/research/) —
start with [`00-executive-summary-and-roadmap.md`](docs/research/00-executive-summary-and-roadmap.md).

> **Current stage: roadmap stage 0 — offline MVP.** Pure Python, standard library
> only, no network calls. It reads local sample files under `data/raw/`, runs the
> full pipeline, and writes JSON + a Markdown digest to `data/processed/`.

## Pipeline

```
collect → normalize → dedup → generate → score → rank → export
```

| Stage | Module | What it does |
|-------|--------|--------------|
| collect   | `collect.py`   | Load raw records from the 3 sources (offline files) |
| normalize | `normalize.py` | → structured `Signal`; lift a `pain_statement`; assign stable id + dedup key |
| dedup     | `dedup.py`     | Drop exact + near-duplicate signals ("already seen") |
| generate  | `generate.py`  | Over-generate idea candidates per signal (rule-based backend) |
| score     | `factors.py` + `ranks.py` | Pure factor functions → weighted, time-decayed `alpha` |
| rank      | `ranks.py`     | MMR re-ranking for novelty **and** diversity |
| export    | `export.py`    | Write `ideas.json` (machine, for idea-evl) + `ideas.md` (human digest) |

The **factor library** (`factors.py`) is the single source of truth for how an
idea is scored, and is meant to be shared verbatim with `idea-evl` so the two
repos never drift.

## Install & run

```bash
pip install -e .

# Run the full pipeline against the bundled sample data
idea-factory

# Options
idea-factory --date 2026-06-13 --top-n 15 --output-dir /tmp/out
idea-factory --sources external_event brain_inbox   # subset of sources
python -m idea_factory                              # equivalent module form
```

Output lands in `data/processed/ideas.json` and `data/processed/ideas.md`.

## The three sources (`data/raw/`)

| Source | File | Confidence |
|--------|------|------------|
| External events | `sample_signals.json` | real |
| Founder's inbox | `inbox.jsonl` (one idea per line) | real |
| Simulated pain  | `personas.json` | **synthetic** (flagged, treated with suspicion) |

Live external sources (Hacker News / arXiv / GitHub Trending RSS, …) are roadmap
stage 1 and will sit behind an explicit, opt-in `collect` command — **never** on
this default offline path.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Non-goals (this stage)

No web UI, no database service, no heavy multi-agent framework, no network on the
default path. These are deferred to later roadmap stages and only added when the
roadmap reaches them. See `docs/research/00-...` §6.
