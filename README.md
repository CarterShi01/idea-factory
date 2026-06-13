# Idea Factory

A two-half system that turns **three sources of signal** — external events, the
founder's own ideas, and simulated target-user pain — into a **screened daily
list of startup ideas**, each with a verdict and a cheap test to run next.

The design, the open-source landscape it borrows from, and the staged roadmap
are in [`docs/research/`](docs/research/) — start with
[`00-executive-summary-and-roadmap.md`](docs/research/00-executive-summary-and-roadmap.md).

> **Current stage: roadmap stage 0 — offline MVP.** Pure Python, standard library
> only, no network calls. Reads local sample files under `data/raw/` and writes
> to `data/processed/`.

## Three isolated packages (`src/`)

```
        ┌─────────────┐
        │  idea_core  │  shared contract: data model + factor library
        └─────────────┘  (single source of truth — no factor drift)
           ▲         ▲
           │         │            idea_gen and idea_eval depend on idea_core,
   ┌───────┘         └───────┐    but never on each other.
┌──────────┐           ┌───────────┐
│ idea_gen │ ──ideas──▶│ idea_eval │
└──────────┘  .json    └───────────┘
 generation              evaluation
 + scoring               + kill-gate
```

| Package | Role | Pipeline |
|---------|------|----------|
| `idea_core` | Shared `models` + `factors` (the contract) | — |
| `idea_gen`  | Generate & score candidates ("alpha" side)  | collect → normalize → dedup → generate → score → rank → export |
| `idea_eval` | Screen candidates, say no efficiently        | read `ideas.json` → kill-gate + rubric → `screened.json` + `decision_memos.md` |

The two halves talk **only through files on disk** (`ideas.json`), so they stay
cleanly isolated. The factor *definitions* live once, in `idea_core`, and are
shared by both — the freqtrade lesson from the research (no drift between the
generation and evaluation sides).

## Install & run

```bash
pip install -e .

# 1. Generate + score candidates  ->  data/processed/ideas.json + ideas.md
idea-gen

# 2. Screen them into decision memos  ->  data/processed/screened.json + decision_memos.md
idea-eval

# End to end, one line:
idea-gen && idea-eval
```

Useful flags:

```bash
idea-gen  --date 2026-06-13 --top-n 15 --sources external_event brain_inbox
idea-eval --date 2026-06-13 --top-n 20 --floor 0.25
python -m idea_gen      # module form
python -m idea_eval
```

## The three sources (`data/raw/`)

| Source | File | Confidence |
|--------|------|------------|
| External events | `sample_signals.json` | real |
| Founder's inbox | `inbox.jsonl` (one idea per line) | real |
| Simulated pain  | `personas.json` | **synthetic** (flagged, screened with extra suspicion) |

Live external sources (Hacker News / arXiv / GitHub Trending RSS, …) are roadmap
stage 1 and will sit behind an explicit, opt-in collect step — **never** on this
default offline path.

## How an idea is judged

`idea_core/factors.py` defines six pure factor functions (`candidate → float`):
`market_freshness`, `pain_intensity`, `build_cost`, `moat_signal`,
`competition_density`, `distribution_fit`.

- **idea_gen** weights them into an `alpha` (with time decay + diversity ranking).
- **idea_eval** applies a **multiplicative-floor kill gate**: a fatal flaw on a
  critical dimension (no real pain, or not solo-buildable) kills the idea
  outright, then scores the survivors and attaches the riskiest assumption + a
  ≤2-week / ≤\$100 test.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Non-goals (this stage)

No web UI, no database service, no heavy multi-agent framework, no network on the
default path. Deferred to later roadmap stages; see `docs/research/00-...` §6.
