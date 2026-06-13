# CLAUDE.md

You are a development executor for the **Idea Factory** repository.

## What this project is (30-second read)

Idea Factory turns **three sources of signal** — external events, the founder's
own ideas, and simulated target-user pain — into a ranked daily list of
structured startup-idea candidates. It is the **generation + factor-scoring**
half of a two-repo system; the sibling `idea-evl` repo is the **evaluation /
kill-gate** half. Together they aim to produce 10–20 vetted startup ideas a day
for a solo software-and-investing founder.

The design, the open-source landscape it borrows from, and the staged roadmap
live in `docs/research/` (read `00-executive-summary-and-roadmap.md` first).

**Current stage: roadmap stage 0 — offline MVP.** Pure Python, standard library
only, no network calls. Reads `data/raw/`, runs the pipeline, writes
`data/processed/`.

## Required reading

1. This file
2. `README.md` — install / run / pipeline overview
3. `docs/research/00-executive-summary-and-roadmap.md` — system blueprint, roadmap, non-goals

By task type, also read the module(s) you touch plus `pipeline.py` to see how
stages compose.

## The pipeline (and what lives where)

```
collect → normalize → dedup → generate → score → rank → export
```

| Path | Purpose |
|---|---|
| `src/idea_factory/models.py` | Data model (`Signal`, `IdeaCandidate`, `ScoredCandidate`). No business logic. |
| `src/idea_factory/collect.py` | Stage 1: load raw records from the 3 sources. **Offline only.** |
| `src/idea_factory/normalize.py` | Stage 2: raw → `Signal`; lift `pain_statement`; stable id + dedup key |
| `src/idea_factory/dedup.py` | Stage 3: drop exact + near-duplicate signals |
| `src/idea_factory/generate.py` | Stage 4: over-generate candidates (pluggable backend; default rule-based) |
| `src/idea_factory/factors.py` | The factor library — pure `candidate → float` functions. **Single source of truth.** |
| `src/idea_factory/ranks.py` | Stage 5: weighted + time-decayed alpha; MMR diversity ranking |
| `src/idea_factory/export.py` | Stage 7: write `ideas.json` (for idea-evl) + `ideas.md` (human) |
| `src/idea_factory/pipeline.py` | Orchestrates the stages |
| `src/idea_factory/cli.py` / `__main__.py` | Thin CLI entry |
| `data/raw/` | Sample inputs (extend only with synthetic data) |
| `data/processed/` | Generated output — never hand-edit; regenerate via the pipeline |
| `docs/research/` | Design + landscape research (do not delete) |
| `tests/` | Test suite (extend when adding logic) |

## Task execution workflow

1. Read the required docs. Restate the task briefly.
2. Sketch a short plan before editing.
3. Make the smallest reasonable change.
4. Keep the offline contract: no network calls on the default pipeline path.
5. Run checks:
   - `pip install -e ".[dev]"`
   - `idea-factory` (smoke-test end to end)
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
- Console entry point: `idea-factory = "idea_factory.cli:main"`. Keep `cli.py`
  thin — parse args, delegate to `pipeline.py`.
- **Standard library only** at this stage; dependencies declared in
  `pyproject.toml` only. Add a dependency only when a task genuinely needs it.
