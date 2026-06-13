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

## LLM steps (A: generate · B: judge)

Two steps can use an LLM, both off by default (the offline rule-based path needs
no network and no tokens). Switch them on per backend:

```bash
# A: LLM generation backend (idea-gen)
idea-gen  --gen-backend router      # Tencent LKEAP (automatable; NOT Claude Code)

# B: LLM-as-judge over the kill-gate survivors only (idea-eval, token-thrifty)
idea-eval --judge-backend router
```

Backends: `rule`/`none` (offline default) · `router` (Tencent) · `mock` (tests) ·
`cc` (manual Claude Code handoff). Prompts + JSON schemas live in
`config/llm/{generate,judge}.json`. Configure the endpoint via env
`IDEA_LLM_BASE_URL` / `IDEA_LLM_API_KEY` / `IDEA_LLM_MODEL` — these fall back to
the standard `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL`, so an ambient
OpenAI-compatible endpoint works out of the box. (`base_url` must include the
version path, e.g. `.../v1`.)

### CC handoff mode (`--*-backend cc`) — no programmatic Claude Code

Per the hard constraint (only manual CC sessions count toward the Max pool), the
`cc` backend **never invokes Claude Code**. It writes a self-contained request
pack and stops:

```bash
idea-eval --judge-backend cc
#  ⏸ writes data/llm_jobs/judge-<date>.request.jsonl and pauses
#  → in a Claude Code session, run:  /run-llm-batch
#    (the run-llm-batch skill reads the pack, judges the whole batch in this
#     session, writes data/llm_jobs/judge-<date>.response.jsonl)
idea-eval --judge-backend cc        # re-run: resumes from the response pack
```

One file = the whole batch = one manual touchpoint. The
[`/run-llm-batch`](.claude/skills/run-llm-batch/SKILL.md) skill automates the
fill step inside CC. See
[`docs/design/llm-abstraction.md`](docs/design/llm-abstraction.md).

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
