# Idea Factory

An eight-stage funnel that turns **money-flow signals** — hiring posts, market
transactions, competitor reviews, HN, the founder's inbox, simulated user pain —
into **one evidence-backed, 48h-testable opportunity per week**. The end metric
is time-to-first-revenue.

The blueprint lives in [`docs/design/pipeline-v2-plan.md`](docs/design/pipeline-v2-plan.md);
background research in [`docs/research/`](docs/research/).

> **Offline by default.** Pure Python, standard library only, no network calls
> on the default path. Reads `data/raw/`, writes stage artifacts to
> `data/processed/`, logs everything to `data/ledger/`.

## One package, eight stages (`src/idea_factory/`)

```
contract ← runtime ← factors ← stages ← pipeline ← cli      (分层铁律,CI 强制)

①recall → ②triage → ③generate → ④rank ──ideas.json──▶ ⑤enrich → ⑥diligence → ⑦portfolio
 捞信号     硬杀      候选成型     纯代码粗排   便宜/昂贵缝   取证+证据门   开庭裁决      组合+周报
                                                     (⑧retro 回流:idea retro / stats / calibrate)
```

Every stage boundary is a **disk artifact** with a uniform envelope
(`schema_version` checked on load): `recall.json → triage.json →
candidates.json → ideas.json → evidence.json → verdicts.json → screened.json`
plus human reports (`ideas.md`, `decision_memos.md`, `weekly_report.md`).
That makes any stage independently rerunnable and the whole run resumable.

Stages never import each other (a CI test enforces it); only `pipeline.py`
composes them. The factor library (`factors/`) is a set of pure
`candidate → float` functions shared by every stage — no scoring drift.

## Install & run

```bash
pip install -e .

idea run                      # the whole funnel, offline, zero tokens
idea run --date 2026-07-07 --top-n 15 --sources brain_inbox
idea run --from enrich        # resume from the expensive half (reads ideas.json)
idea run --only diligence     # re-run exactly one stage from its artifacts
python -m idea_factory run    # module form

idea stats                    # funnel survival / kill reasons / prediction error
idea retro --candidate <id> --metric signups --actual 7   # record a real test result
idea calibrate                # factor↔outcome correlation (read-only, needs ≥10 samples)
```

## LLM steps (all off by default — the offline path costs zero tokens)

Per the cost-gradient first principle, each LLM step is gated by a backend flag;
`none`/`rule` means that step runs deterministic code only:

```bash
idea run --generate-backend router        # ③ LLM candidate generation (Tencent router)
idea run --judge-backend router           # ⑥ critique + judge over gate survivors
idea run --persona-pressure-backend mock  # ⑥ advisory persona objections
idea run --persona-backend router         # ① grounded persona-pain synthesis
```

Backends: `rule`/`none` (offline default) · `router` (Tencent; the automatable
one) · `mock` (tests) · `dify` (Dify workflow; prompts live in `dify/flows/`,
`config/llm/*.json` is the mirror — keep both in sync, CI checks it) · `cc`
(manual Claude Code handoff).

### CC handoff mode (`--*-backend cc`) — no programmatic Claude Code

The `cc` backend **never invokes Claude Code**. It writes a self-contained
request pack and stops:

```bash
idea run --judge-backend cc
#  ⏸ writes data/llm_jobs/judge-<date>.request.jsonl and pauses
#  → in a Claude Code session, run:  /run-llm-batch
idea run --judge-backend cc   # re-run: resumes from the response pack
```

## How an idea is judged

- **②triage** (always on): exact/near-dup dedup + >24-month staleness are hard
  red-lines — no partial credit.
- **④rank**: factor-weighted alpha with time decay and a commodity
  hard-penalty; per-source weight buckets (`config/funnel.json`).
- **⑤enrich** (always on, fixture-backed offline): every rank survivor gets a
  money-evidence chain (competitor pricing / hiring / deals); the **evidence
  gate** requires paying-proof + pricing + reach-path.
- **⑥diligence**: rule kill-gate first (fatal flaw on a critical dimension
  kills outright), then optional devil's-advocate critique + LLM judge, then
  code-enforced discipline: hallucinated citations stripped, un-cited kills
  demoted, ungrounded pursues demoted, batch pursue-fraction capped.
- **⑦portfolio**: quota-driven diversify (中文为主, per-edge caps) + the weekly
  report where every claim links to its evidence.
- **⑧retro**: real test results flow back; `stats`/`calibrate` read the ledger.

## Tests

```bash
pip install -e ".[dev]"
pytest        # includes test_stage_isolation.py — the layering law is CI-enforced
```

## Non-goals (this stage)

No database service, no heavy multi-agent framework, no network on the default
path. See `CLAUDE.md` for the hard rules and design principles.
