# CLAUDE.md

You are a development executor for the **Idea Factory** repository.

## What this project is (30-second read)

Idea Factory 把"钱在流动的地方"的信号(招聘/成交/评论/HN/创始人 inbox/模拟人群)
变成**每周 1 条带钱证据链、48 小时可开测的机会**;终极指标是第一笔收入时间。
北极星与八段设计见 `docs/design/pipeline-v2-plan.md`(唯一施工依据)。

**单包八段架构**(2026-07-07 从零重构,取代旧三包设计):

```
src/idea_factory/
  contract ← runtime ← factors ← stages(八段) ← pipeline ← cli
```

八段漏斗:①recall → ②triage → ③generate → ④rank ──ideas.json──▶
⑤enrich → ⑥diligence → ⑦portfolio(+ ⑧retro 回流,CLI 侧)。
**每个阶段边界落盘一个工件**(统一信封 + schema_version 校验),所以任意段可单独
重跑(`idea run --only diligence`)、断点续跑(`--from enrich`)。

**Current stage: 离线默认。** Pure Python, standard library only, no network
calls on the default path. Reads `data/raw/`, writes stage artifacts to
`data/processed/`, logs to `data/ledger/`.

## Required reading

1. This file
2. `README.md` — install / run / pipeline overview
3. `docs/design/pipeline-v2-plan.md` — 北极星、八段规格、施工状态(§9)

By task type, also read the stage package(s) you touch (each stage's
`__init__.py` docstring states its mission + artifact I/O) plus `pipeline.py`.

## What lives where

```
idea run:  recall → triage → generate → rank → enrich → diligence → portfolio
           (recall.json → triage.json → candidates.json → ideas.json
            → evidence.json → verdicts.json → screened.json + reports)
```

| Path | Purpose |
|---|---|
| `src/idea_factory/contract/` | 层0 数据契约:`models.py`(Signal/IdeaCandidate/ScoredCandidate/Evidence/Outcome/Evaluation + verdict 常量)· `artifacts.py`(阶段边界工件信封)· `stage.py`(StageContext/StageResult)。改字段=改契约=创始人点头。 |
| `src/idea_factory/runtime/` | 层1 横切基建:`llm.py`(batch-first 多后端 + backend_for_step)· `ledger.py`(四张 append-only 日志+trace)· `versioning.py` · `config.py`(founder/funnel/sources 统一加载)· `textsim.py` · `state.py`/`trends.py`/`personas.py` |
| `src/idea_factory/factors/` | 层2 因子库——纯 `candidate → float` 函数,**单一真相源,各段共用** |
| `src/idea_factory/stages/recall/` | ①捞信号:collect + normalize + channels/(adapter 注册表,加源=加文件+注册一行)+ persona/ |
| `src/idea_factory/stages/triage/` | ②硬杀(常开):精确/近重去重 + >24月过期红线;use_state 动态模式 |
| `src/idea_factory/stages/generate/` | ③候选成型:rule(离线夹具)/ llm(per-source 分叉+跨源融合)/ fusion;候选 anti-fit 红线在本段 |
| `src/idea_factory/stages/rank/` | ④纯代码粗排:score(分桶权重×衰减×commodity罚)+ select(MMR/coarse/去聚类)→ ideas.json |
| `src/idea_factory/stages/enrich/` | ⑤取证(常开,fixture 默认):base + pricing/hiring/deals fetcher + 证据门 |
| `src/idea_factory/stages/diligence/` | ⑥开庭:gate(规则前闸)+ critique + judge + enforce(引证/接地/强制分布)+ persona_pressure |
| `src/idea_factory/stages/portfolio/` | ⑦组合出口:diversify(配额打散)+ report(decision_memos/weekly_report)+ 版本快照 |
| `src/idea_factory/stages/retro/` | ⑧回流:outcomes + stats + calibrate(只读,样本不足明确拒绝) |
| `src/idea_factory/pipeline.py` | 唯一编排者:任意连续段区间;跨段胶水(如 use_state 人群回喂)只住这里 |
| `src/idea_factory/cli.py` | 单 CLI `idea {run,retro,stats,calibrate}`,薄壳 |
| `config/llm/*.json` | LLM 步骤的 prompt+schema(⚠️ prompt 正文锁在 `dify/flows/*.yml`,此处是镜像,两处必须同步——CI 有钉) |
| `config/{founder,funnel,sources}.json` | 画像 / 漏斗参数 / 召回源开关(经 runtime.config 读,env 可覆盖) |
| `data/raw/` | 样例输入与离线夹具(extend only with synthetic data) |
| `data/processed/` | 阶段工件 + 报告 + versions/ — never hand-edit; regenerate via `idea run` |
| `data/ledger/` | impressions/verdicts/outcomes/feedback 四张日志 + traces/(常开)。feedback=富反馈+冻结血统快照,供人工在 CC 盘 case 优化,不自动回流 |
| `studio/` | WebUI(server 读工件与 ledger;/api/run 映射段区间) |
| `docs/research/` | 设计与调研(do not delete);`reference-scan/` 是开源参考调研(00-summary §3 = skip 负面清单,防重爬) |
| `reference/` | ★开源参考源(只挖不跑):`sources.yaml` 注册表 + `mirrors/`(submodule 钉 commit)+ `miners/<id>.md`(per-source 挖矿沉淀)+ `sync-source.sh`。纪律见其 README;挖矿用 `/mine-reference <id>`;**永不运行镜像代码、永不自动跟随上游、promote 一律 HITL** |
| `tests/` | 测试套件;`test_stage_isolation.py` 钉死分层铁律,`test_dify_mirror_invariant.py` 钉死 prompt 镜像,`test_reference_registry.py` 钉死参考源注册表 |

**Isolation rule(分层铁律,CI 强制)**:`contract ← runtime ← factors ← stages
← pipeline ← cli` 只许向下依赖;**八段兄弟互不 import**,只能 import
contract/runtime/factors;组合只发生在 `pipeline.py`。跨段通信只经磁盘工件。

## Task execution workflow

1. Read the required docs. Restate the task briefly.
2. Sketch a short plan before editing.
3. Make the smallest reasonable change.
4. Keep the offline contract: no network calls on the default pipeline path.
5. Run checks:
   - `pip install -e ".[dev]"`
   - `idea run`(离线全漏斗冒烟;带 LLM 段用 `idea run --judge-backend mock`)
   - `pytest`
6. Update the PR summary: What changed · Why · How tested · Risks · Follow-up.

## Hard rules

- All code changes go through a PR; the GitHub Action pushes to `claude/issue-<N>-*`
  branches. Do not push directly to the default branch **unless the human owner
  explicitly instructs it in-session.**
- Do not deploy; do not touch secrets, credentials, tokens, billing, or DNS.
- Do not add real external API calls to the default pipeline without explicit
  human approval (live sources are opt-in via `--live`, and the live fetcher
  bodies themselves still need founder sign-off).
- **Never invoke Claude Code programmatically** (no headless `claude -p`, no SDK,
  no bridge/dispatcher). As of 2026-06-15 only manual interactive CC sessions
  count toward the Max pool. The kernel may only reach CC via the file-based
  `CCHandoffBackend` (write a request pack, stop; a human runs CC by hand and
  writes the response pack). LLM automation must go through `RouterBackend`
  (Tencent), which is not CC.
- High-risk or scope-expanding actions require human approval first.

## Core design principles (keep these intact)

- **FIRST PRINCIPLE — LLM cost gradient down the funnel(成本梯度第一原则)**:
  every stage's *semantic judgment* comes from LLM-produced structured fields;
  every stage's *logic* (thresholds, ranking, gates, budgets) is deterministic
  code over those fields. Per-idea LLM cost must increase monotonically down
  the funnel — early stages spend little per idea (batch, small models, single
  extraction) on many ideas; late stages spend a lot per idea (retrieval-backed
  evidence, top models, multi-turn adversarial judging) on few survivors. Cheap
  money filters early so expensive money is only ever spent on the previous
  stage's survivors. Corollary: per-stage total spend (per-idea cost × volume)
  should stay roughly flat; a stage whose total blows up means the *previous*
  stage isn't killing enough — fix the funnel ratio, don't downgrade the model.
  A stage with zero new LLM calls (rank, portfolio) is not a violation: it runs
  on fields already paid for upstream.
- **Factors are pure functions, single source of truth** (`factors/`), so the
  scoring shared across stages never drifts (the freqtrade lesson).
- **Generation over-produces; quality gating is downstream's job** (gate /
  diligence), not the generate stage's.
- **Every stage boundary is a disk artifact**: explicit I/O contract, single-stage
  rerun, resume, what-if — and the future reference-miner 机制 gets a stable
  landing zone per stage.
- **Time matters**: every signal carries a date; alpha decays with age; >24-month
  signals/evidence are hard-killed/invalidated.
- **Personas are synthetic and suspect**: flagged `confidence=synthetic`, held to
  a higher evidence bar everywhere.
- **标签回流常开**: ledger(impressions/verdicts/outcomes/traces)每次跑都写;
  UI 操作即标签。

## Non-goals at this stage

No database service, no heavy multi-agent framework, no network on the default
path, no user accounts / payment / deployment automation. Add these only when
the roadmap explicitly reaches the corresponding stage; if a task seems to need
one, stop and ask rather than scoping up silently.

## Python / packaging conventions

- Python ≥ 3.10, `src/` layout, exposed via `pyproject.toml` setuptools.
- Console entry point: `idea = "idea_factory.cli:main"`(also `python -m
  idea_factory`). Keep `cli.py` thin — parse args, delegate to `pipeline.py`.
- **Standard library only** at this stage; dependencies declared in
  `pyproject.toml` only. Add a dependency only when a task genuinely needs it.
