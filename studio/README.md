# Idea Factory Studio — 可调试控制台（Studio v2）

A web control panel for the idea-factory engine — front/back separated, TS frontend.
**运行为轴的调试台**:每一步挖到了什么、为什么被杀、能否重跑、能否实时追问,全部
可视可查。八段工件模型天生适合可调试(每段边界落盘、run_id 串全链),Studio 把这些
数据接出来重组成一个调试面。

- **Frontend** (`web/`): Vite + React + **TypeScript** SPA(零运行时依赖,单 CSS 文件,
  暗色 quant-terminal 主题)。信息架构 = **运行选择器 → 漏斗首页 → 段钻取 → 单 idea
  全链路血统**,hash 路由深链可书签(`#/run/:id/idea/:x`):
  - **漏斗首页**(RunFunnel):一个 run 的八段 进→存活·杀·存活率条 + 杀因 chip。
  - **段钻取**(StageDrill):某段处理了哪些条目、每条为什么被杀 + 单段重跑(破坏性)。
  - **单 idea 血统**(IdeaLineage):信号原文→候选→因子/alpha→证据门→裁决的纵向时间线;
    每 LLM 步展开看 **prompt+response+token/cost/latency**;星标/杀标签、what-if 重跑评审、
    **实时追问**(就这条 idea 自由提问)都在这里。
- **Backend** (`server/app.py`): **stdlib-only** Python(zero deps)。Imports the
  kernel in-process, serves the built SPA + a JSON API, gated by a single shared
  password (nginx does not auth). Listens on `127.0.0.1:3010`.

> 成本梯度可度量:LLM 段的 trace 现在记 token/cost/latency(见根目录 `config/llm/prices.json`
> ——**创始人自己填每模型单价**,似 founder.json;未填 → 前端显示「未计价」不假装 0)。
> 便宜段(generate)每条 ~百 token、昂贵段(diligence)每条数千 token,沿漏斗单调递增
> 一眼可见。

## Develop

```bash
# backend (terminal 1)
STUDIO_PASSWORD=dev python3 studio/server/app.py

# frontend dev server with hot reload (terminal 2) — proxies /api to :3010
cd studio/web && npm install && npm run dev   # http://localhost:5174
```

## Build + run (single origin)

```bash
cd studio/web && npm install && npm run build   # -> studio/web/dist
STUDIO_PASSWORD='a-strong-password' python3 studio/server/app.py   # serves dist + /api on :3010
```

## API

**运行为轴的观测端点(Studio v2):**

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/runs` | 所有已知运行(版本快照 ∪ ledger),运行选择器数据源 |
| GET  | `/api/run/<run_id>` | 该 run 的八段漏斗:每段 进/存活/杀/存活率 + 杀因分布 + 裁决分布 |
| GET  | `/api/run/<run_id>/stage/<stage>` | 段钻取:该段每条目 event/killed_by(+ 证据门缺项) |
| GET  | `/api/run/<run_id>/idea/<id>` | 单 idea 全链路血统(信号→候选→因子→证据→裁决 + critique/judge/ask trace + 创始人标签) |
| POST | `/api/run/stage` `{stage, from?, to?, ...}` | **破坏性**单段/区间重跑(覆盖工件 + 追加 ledger,run_id 从上游继承) |
| POST | `/api/ask` `{run_id, idea_id, question, backend?}` | **实时追问**:就这条 idea 自由提问,router 即时(未配→mock 兜底),落 trace(stage=ask) |

**动作与旧读端点(保留):**

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/me` · POST `/api/login` `/api/logout` | 鉴权(签名 cookie 会话) |
| POST | `/api/run/generate` `{backend,sources,top_n}` | 跑 recall→rank |
| POST | `/api/run/evaluate` `{backend,floor,top_n}` | 跑 enrich→portfolio |
| POST | `/api/ledger/label` `{candidate_id,action}` | 星标/杀 = 写 ledger 当标签(操作即标签) |
| POST | `/api/run/whatif-judge` | 非破坏性 judge 单段 what-if(不写盘) |
| GET  | `/api/ledger/{funnel,verdicts,outcomes,trace}` | ledger 只读视图 |
| PUT  | `/api/founder-profile` | 编辑 config/founder.json |
| GET  | `/api/top3` | **machine endpoint** — 今日 top-3 非淘汰 idea,稳定 schema(只读,Bearer 鉴权) |
| GET  | `/api/bets` | **machine endpoint** — 最新 run 的完整下注说明书(bet_memos.json 原样,只读,Bearer 鉴权) |
| POST | `/api/outcome` | **machine endpoint** — oc 推送赌局结果(agent-service-plan.md §2.3),`event_id` 幂等,Bearer 鉴权 |

`/api/top3` / `/api/bets` / `/api/outcome` are for downstream agents (oc),
**not** the browser cookie session: `Authorization: Bearer <IDEA_TOP3_API_KEY>`.
`/api/top3` returns `{date, generated_at, count, top3:[{rank, idea_id, title,
one_liner, score, verdict, riskiest_assumption, cheap_experiment}]}` — a
one-liner digest. `/api/bets` is the superset: `{run_id, week, date, count,
bets:[{bet_id, run_id, title, verdict, hypothesis, evidence, riskiest_assumption,
killer_objection, persona_objections, experiment, eval_score, confidence,
lineage_url}]}` — full hypothesis + evidence chain + structured `experiment`
spec (metric/target/kill_below/horizon_days/budget_band), agent-service-plan.md
§2.2's out-bound boundary artifact. Both only read from disk (no generate, no
writes); missing/empty artifact => `200` with an empty list. If
`IDEA_TOP3_API_KEY` is unset both are locked (401 for everyone). Example:

```bash
curl -H "Authorization: Bearer $IDEA_TOP3_API_KEY" http://127.0.0.1:3010/api/top3
curl -H "Authorization: Bearer $IDEA_TOP3_API_KEY" http://127.0.0.1:3010/api/bets
```

`POST /api/outcome` is the in-bound boundary artifact (agent-service-plan.md
§2.3): oc pushes a bet's real-world result after it plays out on its own
kanban — idea-factory never reads oc's board itself, only receives. Body:
`{event_id, candidate_id, tested_at, metric, actual, target?, horizon_days?,
first_revenue?, lesson?, reported_by?}`; `target` auto-fills from the matching
bet memo's `experiment.target` when omitted (same metric only). Idempotent on
`event_id`: a resend is a `200 {"ok":true,"duplicate":true}` no-op, never a
second ledger row — safe to retry.

```bash
curl -X POST -H "Authorization: Bearer $IDEA_TOP3_API_KEY" -H "Content-Type: application/json" \
  -d '{"event_id":"oc-card-1234-final","candidate_id":"<idea_id>","tested_at":"2026-07-20","metric":"signups","actual":4,"reported_by":"oc"}' \
  http://127.0.0.1:3010/api/outcome
```

Env: `STUDIO_PASSWORD` (required for the UI/cookie auth), `STUDIO_PORT` (default
3010), `STUDIO_SECRET` (cookie HMAC; defaults to the password),
`IDEA_TOP3_API_KEY` (Bearer key for `/api/top3`; empty => endpoint locked). Live
LLM runs use the kernel's `IDEA_LLM_*` / `OPENAI_*` (auto-loaded from repo
`.env`). See `.env.example`.

## Deploy on studio.enjoyapier.cloud

The domain currently points to Hermes Studio (127.0.0.1:3001). This panel uses
**3010** so it doesn't clash. `claude-user` is **not** passwordless-sudo and not
in the docker group — the steps below need an operator with sudo.

```bash
# 1. build the frontend
cd studio/web && npm ci && npm run build

# 2. set the panel password (gitignored .env, alongside IDEA_LLM_*)
echo "STUDIO_PASSWORD=<a-strong-password>" >> .env

# 3. run the backend as a service
sudo cp studio/deploy/idea-factory-studio.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now idea-factory-studio
curl -sI http://127.0.0.1:3010/        # sanity: should respond

# 4. point nginx at it (back up the old Hermes Studio conf first)
sudo cp /etc/nginx/sites-available/oc-studio{,.hermes.bak}
sudo cp studio/deploy/studio.enjoyapier.cloud.conf /etc/nginx/sites-available/oc-studio
sudo ln -sf /etc/nginx/sites-available/oc-studio /etc/nginx/sites-enabled/oc-studio
sudo nginx -t && sudo systemctl reload nginx

# 5. (optional) stop the old Hermes Studio container — it's profile-gated, safe to stop
sudo docker compose --profile studio stop hermes-studio   # in ../one-creator
```

Rollback: `sudo cp /etc/nginx/sites-available/oc-studio.hermes.bak /etc/nginx/sites-available/oc-studio && sudo nginx -t && sudo systemctl reload nginx`.

TLS: the existing `enjoyapier.cloud` cert already covers the `studio` SAN — no certbot needed.
