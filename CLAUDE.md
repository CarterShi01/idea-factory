# CLAUDE.md

You are a development executor for the Idea Factory repository.

## What this project is (30-second read)

Idea Factory collects product launch / market signal information and turns it into structured startup idea candidates. It is intended to grow into a lightweight AI-agent-driven idea production pipeline.

**Current stage: Early offline demo.** The pipeline runs against a local sample file (`data/raw/sample_products.json`), normalizes records, generates mock idea candidates, and writes JSON / Markdown to `data/processed/`. No external APIs are called yet.

This repository is one of the projects managed by **CreatorMesh**. Tasks usually arrive as GitHub issues dispatched by CreatorMesh; the `@claude` mention in an issue comment triggers the Claude Code GitHub Action defined in `.github/workflows/claude.yml`.

## Required reading

**Every task:**

1. This file (`CLAUDE.md`)
2. `README.md` — install / run instructions, current CLI surface
3. `docs/project-brief.md` — goals, early demo scope, and **explicit non-goals**

**By task type (add to the above):**

| Task type | Additional reading |
|-----------|-------------------|
| Touching `src/idea_factory/` | The specific module(s) you are changing, plus `pipeline.py` to see how stages compose |
| Adding a new pipeline stage | `pipeline.py`, then `normalize.py` / `generate.py` / `ranks.py` as reference patterns |
| Changing CLI behavior | `cli.py` and `__main__.py` |
| Changing data shapes | `normalize.py`, `export.py`, and the sample files in `data/raw/` |

## Task execution workflow

1. Read the required documents above.
2. Restate the task briefly in your first response.
3. Sketch a short implementation plan before editing files.
4. Make the smallest reasonable change that satisfies the task.
5. If you add or change a stage, keep the offline-only contract: do not introduce network calls in the demo path.
6. Run available checks when relevant:
   - `pip install -e .`
   - `idea-factory` (smoke-test the pipeline end-to-end)
   - `python -m idea_factory.cli --input data/raw/sample_products.json --output-dir /tmp/idea-out` (alternate invocation)
7. Create or update a PR summary: What changed · Why · How tested · Risks · Follow-up tasks.

## Hard rules

- Do not merge into the default branch.
- Do not deploy anything.
- Do not touch secrets, credentials, tokens, billing, or DNS.
- Do not add real external API calls to the demo pipeline without explicit human approval (the demo is intentionally offline).
- All code changes must go through PR. The GitHub Action will push to `claude/issue-<N>-*` branches; do not push directly to the default branch.
- High-risk or scope-expanding actions require human approval before execution.

## Early demo principles (non-goals)

Per `docs/project-brief.md`, the first demo deliberately does **not** include:

- A web UI
- A database
- A complex multi-agent framework
- User accounts or payment
- Deployment automation

Do not introduce any of these as a side effect of a smaller task. If a task seems to require one, stop and ask in the PR / issue rather than scoping up silently.

## Python / packaging conventions

- Python ≥ 3.10. Package layout follows `src/` layout (`src/idea_factory/`), exposed via `pyproject.toml` setuptools `packages.find`.
- Console entry point: `idea-factory = "idea_factory.cli:main"`. Keep `cli.py` thin — it should parse args and delegate to `pipeline.py`.
- Dependencies are declared in `pyproject.toml` only. Do not add a separate `requirements.txt`.
- Prefer the standard library where reasonable; only add a new dependency when it is genuinely needed for the task at hand.

## What lives where

| Path | Purpose |
|---|---|
| `src/idea_factory/pipeline.py` | Orchestrates the stages (normalize → generate → rank → export) |
| `src/idea_factory/normalize.py` | Raw record → structured record |
| `src/idea_factory/generate.py` | Structured records → idea candidates |
| `src/idea_factory/ranks.py` | Scoring / ordering of candidates |
| `src/idea_factory/export.py` | Writes JSON / Markdown output |
| `src/idea_factory/cli.py` / `__main__.py` | Command-line entry |
| `src/idea_factory/api.py` | Reserved / experimental — not part of the demo pipeline |
| `data/raw/` | Sample input fixtures — safe to read, only extend with synthetic data |
| `data/processed/` | Generated output — never hand-edit; regenerate via the pipeline |
| `tests/` | Test suite (extend here when adding logic) |
