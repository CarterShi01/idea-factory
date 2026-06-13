# CLAUDE.md

You are a development executor for the **Idea Factory** repository.

## What this project is (30-second read)

Idea Factory turns **three sources of signal** — external events, the founder's
own ideas, and simulated target-user pain — into a **screened daily list of
startup ideas**, each with a verdict and a cheap next test. It aims to produce
10–20 vetted ideas a day for a solo software-and-investing founder.

It is **one repo with two halves**, kept as isolated packages that share only a
contract:

- `idea_core` — shared data model + factor library (single source of truth)
- `idea_gen`  — generation + factor-scoring (the "alpha" side)
- `idea_eval` — evaluation + kill-gate (says no efficiently)

`idea_gen` and `idea_eval` both depend on `idea_core` but **never on each other**;
they communicate only through `data/processed/ideas.json` on disk.

The design, the open-source landscape it borrows from, and the staged roadmap
live in `docs/research/` (read `00-executive-summary-and-roadmap.md` first).

**Current stage: roadmap stage 0 — offline MVP.** Pure Python, standard library
only, no network calls. Reads `data/raw/`, runs the pipelines, writes
`data/processed/`.

## Required reading

1. This file
2. `README.md` — install / run / pipeline overview
3. `docs/research/00-executive-summary-and-roadmap.md` — system blueprint, roadmap, non-goals

By task type, also read the module(s) you touch plus `pipeline.py` to see how
stages compose.

## What lives where

```
idea_gen:  collect → normalize → dedup → generate → score → rank → export  ──ideas.json──▶
idea_eval: read ideas.json → kill-gate + rubric → screened.json + decision_memos.md
```

| Path | Purpose |
|---|---|
| `src/idea_core/models.py` | Data model (`Signal`, `IdeaCandidate`, `ScoredCandidate`). No business logic. |
| `src/idea_core/factors.py` | The factor library — pure `candidate → float` functions. **Single source of truth, shared by both halves.** |
| `src/idea_core/llm.py` | Provider-neutral, batch-first LLM abstraction (router/CC-handoff/mock backends). See `docs/design/llm-abstraction.md`. |
| `config/llm/*.json` | Config-driven prompts + schemas for the LLM steps (generate / judge) |
| `src/idea_gen/collect.py` | Stage 1: load raw records from the 3 sources. **Offline only.** |
| `src/idea_gen/normalize.py` | Stage 2: raw → `Signal`; lift `pain_statement`; stable id + dedup key |
| `src/idea_gen/dedup.py` | Stage 3: drop exact + near-duplicate signals |
| `src/idea_gen/generate.py` | Stage 4: over-generate candidates (pluggable backend; default rule-based) |
| `src/idea_gen/ranks.py` | Stage 5: weighted + time-decayed alpha; MMR diversity ranking |
| `src/idea_gen/export.py` | Stage 7: write `ideas.json` (for idea_eval) + `ideas.md` (human) |
| `src/idea_gen/pipeline.py` | Orchestrates the generation stages |
| `src/idea_gen/cli.py` / `__main__.py` | Thin CLI entry (`idea-gen`) |
| `src/idea_eval/evaluate.py` | Kill-gate (multiplicative-floor) + weighted rubric + riskiest-assumption/RAT |
| `src/idea_eval/export.py` | Write `screened.json` + `decision_memos.md` |
| `src/idea_eval/pipeline.py` | Read `ideas.json`, evaluate, write results |
| `src/idea_eval/cli.py` / `__main__.py` | Thin CLI entry (`idea-eval`) |
| `data/raw/` | Sample inputs (extend only with synthetic data) |
| `data/processed/` | Generated output — never hand-edit; regenerate via the pipelines |
| `docs/research/` | Design + landscape research (do not delete) |
| `tests/` | Test suite (extend when adding logic) |

**Isolation rule:** `idea_gen` and `idea_eval` may import `idea_core`, never each
other. Cross-half communication is the `ideas.json` file only.

## Task execution workflow

1. Read the required docs. Restate the task briefly.
2. Sketch a short plan before editing.
3. Make the smallest reasonable change.
4. Keep the offline contract: no network calls on the default pipeline path.
5. Run checks:
   - `pip install -e ".[dev]"`
   - `idea-gen && idea-eval` (smoke-test both halves end to end)
   - `pytest`
6. Update the PR summary: What changed · Why · How tested · Risks · Follow-up.

## Hard rules

- All code changes go through a PR; the GitHub Action pushes to `claude/issue-<N>-*`
  branches. Do not push directly to the default branch **unless the human owner
  explicitly instructs it in-session.**
- Do not deploy; do not touch secrets, credentials, tokens, billing, or DNS.
- Do not add real external API calls to the default pipeline without explicit
  human approval (live sources are opt-in, roadmap stage 1+).
- High-risk or scope-expanding actions require human approval first.

## Core design principles (keep these intact)

- **Factors are pure functions, single source of truth** (`factors.py`), so the
  scoring shared with `idea-evl` never drifts (the freqtrade lesson).
- **Generation over-produces; quality gating is idea-evl's job**, not the
  generate stage's.
- **Time matters**: every signal carries a date; alpha decays with age.
- **Personas are synthetic and suspect**: flagged `confidence=synthetic`.

## Non-goals at this stage

No web UI, no database service, no heavy multi-agent framework, no network on the
default path, no user accounts / payment / deployment automation. Add these only
when the roadmap explicitly reaches the corresponding stage; if a task seems to
need one, stop and ask rather than scoping up silently.

## Python / packaging conventions

- Python ≥ 3.10, `src/` layout, exposed via `pyproject.toml` setuptools.
- Console entry points: `idea-gen = "idea_gen.cli:main"` and
  `idea-eval = "idea_eval.cli:main"`. Keep each `cli.py` thin — parse args,
  delegate to `pipeline.py`.
- **Standard library only** at this stage; dependencies declared in
  `pyproject.toml` only. Add a dependency only when a task genuinely needs it.
