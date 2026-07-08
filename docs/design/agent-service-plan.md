# Agent 服务化改造计划 — idea-factory 作为 oc 的"投研部"

> 状态:创始人与 CC 讨论定稿的施工蓝图(2026-07-08)。
> 上游文档:`pipeline-v2-plan.md`(八段漏斗,本文假定其已落地,见其 §9.6/9.7)。
> 本文回答:idea-factory 如何成为被 oc(one-creator)直接调用的总 Agent。

## §0 定位与边界(创始人已认可,钉死)

**idea-factory = 一人公司的投研部。** 管辖权从"世界的噪音"开始,到"一份可证伪
的下注说明书"为止;此外必须记账并从赌局结果里学习。永远不碰"怎么把事做出来"。

五职责:**发现 · 挖掘 · 论证(出口=下注说明书)· 学习(被动收 outcome)· 可解释**。

**两个边界工件**(与 oc 之间只交换这两种东西):

- 出:**bet memo(下注说明书)**——假设 + 证据链 + 最危险假设 + 实验规格
  (测什么/看什么指标/什么算输赢/预算档)。
- 入:**outcome 事件**——oc push 过来的赌局结果(卡黄了/实验杀掉/收入到账)。

**明确不管**(oc 领土):赌不赌的最终决策(human gate)、实现拆解/派活/排期、
执行实验/建 MVP、观察执行过程与采集 outcome、跨系统编排与 HITL。
"计划"一词从本仓库词汇表删除:**实验定义**(论证收尾)是我们的,
**实现规划**(执行开头)是 oc 的。

检验法:任何一方想多要一点(idea-factory 想指挥执行 / oc 想伸手改判决权重),
都是越界。

### §0.1 当前运行模式(创始人 2026-07-08 拍板)

**近期只有一种用法:每周批量跑一次,出 top idea(现有 `idea-top3-to-cto`
workflow)。** 交互式被 oc 直接调用(validate 我半夜的点子 / deepdive 某领域 /
异步 job / 预算封顶)**先不做**——但**架构必须让它成为"插上去"而非"重建"**:
本轮 M-A/M-B/M-C 的所有产物(bet_memos.json、outcome 收件口、真信号漏斗)都要
按"以后 M-D 意图面直接复用"来设计,不得埋下阻断未来接入的假设。

因此近期施工范围 = **M-A + M-B + M-C**(全部服务每周批量跑);
M-D(意图面)+ M-E(部署硬化)**推迟,但保持插件可接**。

## §1 现状盘点(2026-07-08 逐文件核对)

### ① 发现 — 骨架完整,信号是假的

| 有 | 坐标 |
|---|---|
| 8 个召回 channel + adapter 注册表(加源=加文件+注册一行) | `stages/recall/channels/` |
| **hn_algolia live 已实现**(真代码,`ctx.live` 触网,增量+单源隔离) | `channels/hn_algolia.py` |
| **vps_browser live 已实现**(CDP 挂已登录 Chrome,6 个中文站 targets 已配) | `channels/vps_browser.py` + `config/sources.json` |
| triage 红线常开、trends/state 动态模式 | `stages/triage/`,`runtime/{trends,state}.py` |

| 缺 | 严重度 |
|---|---|
| jobs / marketplace / reviews 的 live 路径 = `return []` 桩("钱在流动"三源全是 fixture) | **致命** |
| vps_browser 运行条件未常态化(socat 桥/选择器按现网 DOM 调,sources.json 里自己注明"首次多半要改") | 高 |
| 周期跑无调度(oc 侧 `idea-top3-cron.sh` 只拉结果,不触发跑) | 中(归 oc) |

### ② 挖掘 — 有合成,无定向,注入口只有半个

| 有 | 坐标 |
|---|---|
| generate rule / llm(per-source 分叉+跨源融合)/ fusion | `stages/generate/` |
| 外部灵感录入 `/api/inbox` → `data/raw/inbox.jsonl`(brain 源下轮吃) | `studio/server/app.py:522` |

| 缺 | 严重度 |
|---|---|
| **定向挖掘**:`pipeline.run()` 无 theme/query 参数,recall 纯源驱动,无法"在 X 领域帮我找" | 高 |
| generate 默认仍 rule,LLM 步骤默认全关(§9.3 待拍板) | 高 |
| inbox 只是"扔进池子等下轮",不是"针对这条走论证"(见④ validate 通道) | 中 |

### ③ 论证 — 机器最全,弹药(证据)是假的

| 有 | 坐标 |
|---|---|
| enrich 证据门(5 类证据、24 月失效)+ diligence 全套(gate/critique/judge/enforce 引证校验/强制分布/persona 压测) | `stages/{enrich,diligence}/` |
| judge schema 已含 `riskiest_assumption`/`cheap_experiment`/`reasons[claim+evidence_ids]` | `config/llm/judge.json` |

| 缺 | 严重度 |
|---|---|
| enrich 三 fetcher(pricing/hiring/deals)live = 桩 → 证据门吃 fixture | **致命** |
| `evidence_structuring` LLM 步(依赖上条) | 高 |
| 单条 idea 的按需论证入口(工件架构天然支持 `--from enrich`,但没有"注入一条→走后半程"的通道) | 高 |

### ④ 出口:bet memo — 比预想近,但不是结构化工件

| 有 | 坐标 |
|---|---|
| `Evaluation.riskiest_assumption` + `cheap_experiment`(gate 规则版兜底,judge LLM 版覆盖) | `contract/models.py:260`,`diligence/{gate,judge}.py` |
| weekly_report 已有"48h 测试包(草稿)"块:渠道(first_10_customers)+ 参考定价(从证据抽)+ 预测占位 | `portfolio/report.py:145` |
| `/api/top3` 稳定机读 schema(已含 riskiest_assumption/cheap_experiment) | `studio/server/app.py:407` |

| 缺 | 严重度 |
|---|---|
| **无结构化实验规格**:cheap_experiment 是自由文本;无 metric/target/horizon/kill 条件/预算档字段 → "可证伪"落不了地 | **高** |
| 无 bet memo 独立工件(weekly_report 是给人读的 markdown;top3 缺证据链与实验结构) | 高 |
| 预测(target)全靠 retro 时人工 `--target` 回填——下注时不写赔率,复盘时才补,时序反了 | 高 |

### ⑤ 学习 — 机器建好,进水管只有人工水龙头

| 有 | 坐标 |
|---|---|
| outcomes ledger + `record_outcome`(回读 verdict 上下文)+ `prediction_error` + stats + calibrate(只读,样本<10 明确拒绝)+ retro_lesson LLM | `stages/retro/`,`runtime/ledger.py:293` |

| 缺 | 严重度 |
|---|---|
| **outcome 收件口**:只有 CLI `idea retro` 人工敲;studio server 无 POST /api/outcome;无幂等键 | **高** |
| oc 侧 push workflow(卡终态→outcome 事件)——oc 仓库的票,本文只定收口契约 | 中(oc) |
| calibrate 永远"样本不足"(上两条的结果,非独立缺口) | — |

### ⑥ 可解释 — 已是强项

`/api/ask`(血统上下文+锁"不编证据"system)、全链路 trace(prompt/response/
token/cost/latency)、run_id 血统、Studio 深链——**已够用,本轮不动**。

### ⑦ agent 服务面(横切)— 有人用的调试台,没有机器用的契约

| 有 | 缺 |
|---|---|
| studio server 全套观测/追问/重跑 API + token/bearer auth;oc 侧 DMZ 消毒代理已验证(idea_factory_top3) | 意图 API 契约(discover/validate/deepdive/outcome);**异步 job 语义**(`/api/run/*` 同步阻塞调 `pipeline.run`,LLM 全开后必超时);**预算参数**(`cost_of` 已有,无 budget 封顶);`prices.json` 单价未填 |

## §2 边界工件规格(M-A 一次定死)

### 2.1 实验规格 `ExperimentSpec` —— 本计划唯一的新契约概念

设计要点:**实验规格与 `Outcome.prediction` 同构**。下注时写的赔率,就是复盘时
对账的口径,`prediction_error` 直接可算——闭环在 schema 层就锁死,不靠纪律。

```json
{
  "action":       "48h 内做什么(落地页/预售帖/人工代跑服务……)",
  "channel":      "在哪测(继承 first_10_customers)",
  "metric":       "signups | preorders | replies | paid …",
  "target":       10,
  "horizon_days": 7,
  "kill_below":   3,
  "budget_band":  "0-500元 | 500-2000元 | 2000元+"
}
```

落点:`Evaluation.experiment: dict`(替代自由文本 `cheap_experiment` 的地位,
旧字段保留只读兼容)。judge LLM 产字段,gate 规则版给保守默认,enforce 校验:
**PURSUE 必须带完整实验规格,缺 → demote REVIEW(`experiment_demoted`)**——
与证据门同一思路:不可证伪的 PURSUE 不配叫 PURSUE。

### 2.2 出向:`bet_memos.json`(portfolio 段新工件,统一信封)

每条 = PURSUE/REVIEW 幸存者的机读收口:

```json
{
  "bet_id": "<idea_id>", "run_id": "…", "title": "…", "verdict": "pursue",
  "hypothesis": {"pain": "…", "solution": "…", "target_user": "…",
                  "why_now": "…", "why_only_me": "…"},
  "evidence": [ …引证过的证据链(含 url/date/valid)… ],
  "riskiest_assumption": "…", "killer_objection": "…",
  "persona_objections": [ … ],
  "experiment": { …ExperimentSpec… },
  "eval_score": 71.5, "confidence": "real",
  "lineage_url": "/#/run/<run_id>/idea/<idea_id>"
}
```

weekly_report 的"48h 测试包"块改为从此工件渲染(单一真相源);
`/api/top3` 保留兼容,新增 `/api/bets`。

### 2.3 入向:outcome 事件(POST /api/outcome)

```json
{
  "event_id":     "oc-card-1234-final",   // 幂等键,重复投递静默去重
  "candidate_id": "<idea_id>",
  "tested_at":    "2026-07-20",
  "metric":       "signups", "actual": 4,
  "target":       null,                    // 省略时从该 idea 的 bet memo 补
  "first_revenue": null, "lesson": "",
  "reported_by":  "oc | founder"
}
```

语义:**采集是 oc 的(push),消化是我们的(被动收→ledger→retro/calibrate)**。
`idea retro` CLI 保留,即此收件口的人工版。idea-factory 永不主动读 oc 看板。

## §3 改造票(五个里程碑)

约定:每票列【改动 / 验收 / 依赖 / 拍板】。全部遵守既有纪律——分层铁律、
离线默认(live/LLM 一律 opt-in)、无数据库(文件即状态)、stdlib only、
**dify 镜像不变式**(动 `config/llm/*.json` 的 prompt/schema 必须同步
`dify/flows/*.yml`,CI 有钉)、PR 流程。

### M-A 出口:下注说明书(先做——不依赖拍板,纯离线可完成,直接喂饱 oc 现有 workflow)

- **A1 契约**:`Evaluation.experiment: dict` + `EXPERIMENT_FIELDS` 常量 +
  校验函数(contract 层);`Outcome.prediction` 语义对齐(不改 shape,注释钉同构)。
  改:`contract/models.py`。验收:schema_version 相关测试 + 向后兼容
  (旧 verdicts.json 反序列化不炸)。
- **A2 diligence 产实验规格**:judge.json schema/prompt 加 `experiment` 对象
  (⚠️ 同步 `dify/flows/idea-judge.yml`);gate 规则版给保守默认;enforce 新增
  `enforce_experiment`(PURSUE 缺完整规格 → demote,`experiment_demoted`)。
  改:`diligence/{gate,judge,enforce}.py`,`config/llm/judge.json`,dify 镜像。
  验收:mock 后端全链路,PURSUE 无规格被降档的用例;dify 镜像不变式测试绿。
- **A3 portfolio 出 bet_memos.json**:diversify 后收口 top-N 幸存者;
  weekly_report 的测试包块改从它渲染。改:`portfolio/{report,__init__}.py`,
  `pipeline.py`(工件登记),versioning 快照名单 +1。
  验收:`idea run` 后 `data/processed/bet_memos.json` 信封合法;周报内容不回退。
- **A4 API**:`GET /api/bets`(最新版工件,DMZ 友好:纯结构化字段,无自由指令
  文本混入);`/api/top3` 不动。改:`studio/server/app.py`。
  验收:oc 侧只需把 workflow 的 tool_ref 从 top3 换 bets 即拿到完整下注说明书。

### M-B 回流:outcome 收件口(小票,与 M-A 并行)

- **B1 收件口**:`POST /api/outcome`(§2.3 schema;幂等:event_id 已见即 200
  返回 `duplicate:true`;target 缺省从 bet memo 补;落 `record_outcome` 同一条
  代码路径)。改:`studio/server/app.py`,`stages/retro/outcomes.py`(提出
  可复用入口),ledger 加 event_id 去重读。
  验收:重复投递不重复记账;`idea stats` 能看到经 API 进来的 outcome。
- **B2 oc 侧 push workflow**(oc 仓库票,本仓库零改动):卡终态/实验结果 →
  POST /api/outcome。本文只锁 §2.3 契约。
- **B3 calibrate 汇报**:样本 ≥ min-sample 时,周报尾部附 calibrate 因子相关性
  摘要(只读,仍不自动改权重)。改:`portfolio/report.py`。

### M-C 地基:真信号(价值最大,拍板已定 → 每票都是"填函数体")

**拍板已定(2026-07-08)**:①live 一律走 **vps_browser 机制**(CDP 挂已登录
Chrome + 加 targets),不走 CC-handoff;②LLM 默认后端一律 **腾讯 router**
(LKEAP tc-code/tc-think),`prices.json` 已按 1亿token=100元 填好
(commit ea3a7a8)。剩下唯一待你逐条给的是**目标站点清单**(合规你判断)。

- **C1 三源 live 接线**:jobs/marketplace/reviews 复用 vps_browser 机制
  (CDP 挂已登录 Chrome + 新 targets:BOSS直聘/闲鱼成交页/竞品评论页),
  **不新写爬虫**。改:三个 channel 的 live 分支 + `config/sources.json` targets。
  验收:`idea run --live --only recall` 产出真实 money_trace 信号;离线默认
  路径字节不变。待给:站点清单(§5-①)。
- **C2 enrich 三 fetcher live**:**执行时收窄了范围,记录在此**——机制决策
  (vps_browser,CC-handoff 已否决)已写进 `enrich/base.py` docstring,但没有
  真接线。原因:C1 的 `fetch_via_browser` 返回的是**信号形状**(title/url/
  category),而 `Evidence` 需要 **keywords(供本模块既有的按候选关键词匹配复用)
  /source_date/numbers**——这些字段依赖真实目标页的结构,没给站点清单之前接线
  是猜,不是"填函数体"。C1(recall 三源)不受影响,因为它们本就是信号形状,
  直接复用 `fetch_via_browser` 零改造(已验证:`idea run --live --only recall`
  跑通,hn_algolia 真实拉回 20 条,jobs/marketplace/reviews 空 targets 优雅返回
  `[]`,无异常)。**站点清单给到后**,这里要额外定一件事:每个 target 配的
  `keywords` 从哪来(config 里手写,还是从页面内容推断)。
- **C3 evidence_structuring LLM 步**:live 原文 → 结构化 Evidence(依赖 C2),
  走腾讯 router。新 `config/llm/evidence.json` + dify 镜像。
- **C4 vps_browser 常态化**:socat 桥固化(devops)、现网选择器实调、
  失败告警进 ledger。批量周跑的可靠性由此票兜底。
- **C5 LLM 默认切腾讯**:**执行时改了口径,记录在此**——没有去改 `idea run`
  裸参数的 argparse 默认值(仍是 `rule`/`none`),而是新增 `scripts/weekly-run.sh`
  作为显式 opt-in 预设(`--live --generate-backend router --judge-backend router
  --persona-backend router --persona-pressure-backend router`)。原因:CLAUDE.md
  硬规则"默认管线路径不得静默加真实外部调用"+"离线默认"是项目身份,`idea run`
  裸调用必须继续对 CI/开发者保持零网络零 token 确定性;创始人"默认先都使用腾讯"
  的决策解读为"批量跑这个动作默认用腾讯",不是"改写 CLI 参数本身的默认值"这个更
  大范围的决定——如果创始人确认要后者,是单独一票(改 `cli.py` 的 `default=`)。
  `prices.json` 已就绪(无待办)。**成本核算**:每周批量一跑,漏斗量级下即便昂贵
  段每条数千 token,单周总量在 1亿token=100元 口径下是分钱级,批量模式无需预算
  封顶(封顶留给未来 M-D 交互式调用)。

### M-D 入口:意图面(把调试台升级为 agent 服务)

- **D1 异步 job 语义**:`POST /api/jobs`(kind=discover|validate,参数→后台
  线程跑 `pipeline.run`,job 状态落 `data/ledger/jobs.jsonl`,文件即状态,无 DB)
  + `GET /api/jobs/<id>`(状态/进度=已完成段/产物指针)。现有同步端点保留
  (兼容 Studio 前端小跑)。验收:LLM 全开的全漏斗经 job 提交不超时,可轮询。
- **D2 validate 通道(外部 idea 注入)**:`POST /api/validate`
  {title, pain, solution?, target_user?} → 铸单条 candidate → 独立
  `data/processed/adhoc/<run_id>/` 写 count=1 的 ideas.json → job 跑
  `--from enrich`(enrich→diligence→portfolio)→ 返回该条 bet memo。
  ledger 照写(kind="validate"),不污染主线工件。
  验收:"论证一下我半夜想的点子"从 API 一次调用拿到判决+说明书。
- **D3 deepdive 通道(定向挖掘)**:`POST /api/jobs` kind=deepdive
  {theme, keywords[]} → 运行时覆盖 sources 配置(hn queries=keywords;
  vps_browser 用 URL 模板生成临时 targets)→ 窄漏斗全程。
  改:`StageContext` 加 `theme_overrides`,recall channels 读它。
  本里程碑最大的新功能,可最后做。
- **D4 预算参数**:`StageContext.budget_cny` + runtime.llm 按 `cost_of` 累计,
  超限 → 停止发起新 LLM 调用、当前段收尾、结果标 `budget_exhausted`。
  验收:budget=0.01 的 job 提前收尾且工件完整可读。
- **D5 oc 侧意图工具扩容**(oc 仓库票):DMZ 代理加
  `idea_factory_{bets,validate,deepdive,ask,outcome}`,沿用已验证的消毒链路。
  暂不 MCP 化(意图稳定后再议)。

### M-E 服务化硬化(最后,量小)

- **E1 API 面分区**:`/api/agent/*` 前缀收拢机器意图(bets/validate/deepdive/
  outcome/jobs),bearer 必须;人用调试端点不动。
- **E2 部署形态**:studio server 常驻化(systemd unit 或并入 oc compose),
  归 oc 拓扑,需与 oc 侧一起定。拍板(§5-③)。

## §4 施工顺序与依赖

```
近期范围(服务每周批量跑):
  M-A 出口(纯离线)──┐
  M-B 回流(纯离线)──┼──▶ M-C 地基(vps_browser 真信号 + 腾讯 LLM)
  ─────────────────┘        │
未来(推迟,保持插件可接):    └──▶ M-D 意图面 ──▶ M-E 部署硬化
```

- **最小可用闭环 = M-A + M-B**:oc 每周拿到结构化下注说明书、outcome 能回流。
  即使信号还是 fixture,边界契约先跑起来,oc 侧 workflow 可同步施工。纯离线,
  可立即开工。
- **价值拐点 = M-C**:信号变真,每周 top idea 才有真产出。拍板已定
  (vps_browser + 腾讯),每票即"填函数体",只等站点清单(§5-①)。
- **M-D / M-E 推迟**:交互式调用近期不做(§0.1)。约束:M-A/M-B/M-C 的产物必须
  让 M-D 直接复用——bet_memos.json 是机读工件、outcome 是 API 端点、
  `pipeline.run` 已支持 `--from enrich`(未来 validate 的入口)与 sources 覆盖
  (未来 deepdive 的入口);不得埋阻断假设。

## §5 拍板状态(2026-07-08 已定)

1. **live 接线** ✅ 定:走 **vps_browser 机制**(不走 CC-handoff)。**唯一待给**:
   目标站点清单(BOSS直聘/闲鱼/竞品定价页/评论页——合规创始人判断),逐个
   给 URL + DOM 选择器即接一个。
2. **LLM 默认档** ✅ 定:默认全切 **腾讯 router**(tc-code/tc-think);
   `prices.json` 已按 1亿token=100元 填好(commit ea3a7a8),无待办。
3. **部署形态 / 交互式接入** ✅ 定:**先不做**,近期只跑每周 top idea;架构保持
   未来可插(§0.1)。等真要交互式接入时再定常驻进程与 DMZ 拓扑。

## §7 施工状态(2026-07-08,同日执行)

创始人 `/goal` 指示"按计划实施整个方案,直到达成设计目标"后,同一会话内完成
M-A + M-B + M-C 的可完成部分。逐票状态:

| 票 | 状态 | 备注 |
|---|---|---|
| A1 契约 | ✅ 完成 | `Evaluation.experiment`/`EXPERIMENT_FIELDS`/`experiment_is_complete`;`Outcome.event_id`/`reported_by` 顺带一起加(同一批 models.py 改动) |
| A2 diligence 产实验规格 | ✅ 完成 | gate.py `_EXPERIMENT_SPEC` 规则默认;judge.py 合并 LLM 覆盖;`config/llm/judge.json` system/schema 加 `experiment`;`dify/flows/idea-judge.yml` 同步(mirror invariant 测试绿) |
| A2b enforce | ✅ 完成 | `enforce_experiment_spec`:PURSUE 缺规格 → demote REVIEW(`experiment_demoted`) |
| A3 bet_memos.json | ✅ 完成 | 新模块 `portfolio/bets.py`;`versioning.py` 快照名单 +1 |
| A3b weekly_report 改渲染 | ✅ 完成 | `_smoke_test_block` 从 `e.experiment` 结构化渲染,不再从证据猜定价;顺手修了一处陈旧引用(`idea-eval retro`→`idea retro`,三包重构后的漏改) |
| A4 GET /api/bets | ✅ 完成 | 复用 `/api/top3` 的 bearer 鉴权 |
| B1 outcome 收件口 | ✅ 完成 | `POST /api/outcome`;`event_already_recorded` 幂等;target 缺省从 bet memo 补 |
| B3 calibrate 摘要 | ✅ 完成 | **执行时发现 §3 原方案会违反分层铁律**(portfolio 直接 import retro.calibrate = 兄弟段互 import,`test_stage_isolation.py` 当场标红)——改为 `pipeline.py`(唯一允许跨段的组合层)计算 `calibrate_report` 纯 dict,经 `StageContext` 注入 portfolio,仿照 `ctx.backends` 的既有先例。portfolio 自身仍零 import retro |
| C5 LLM 默认切腾讯 | ✅ 完成(范围收窄) | 见上方 C5 票内的记录:未改 `idea run` 裸默认,新增 `scripts/weekly-run.sh` 作为显式预设 |
| C1 三源 live 接线 | ✅ 完成 | jobs/marketplace/reviews 复用 `vps_browser.fetch_via_browser`;`config/sources.json` 三源加 `cdp_endpoint`/`targets:[]`;端到端验证(`--live --only recall`)真实拉回 hn 信号、空 targets 源优雅退化,无异常 |
| C2 enrich fetcher live | ⏸️ 机制已定,接线推迟 | 见上方 C2 票内的记录:形状不匹配(信号 vs 证据),没有站点清单前接线是猜测,已在代码里留清晰的后续说明而非假接线 |
| C3 evidence_structuring | ⏸️ 未做 | 依赖 C2 |
| C4 vps_browser 常态化 | ⏸️ 未做 | 需要 devops 权限(socat 桥)+ 真实现网调选择器,超出本次会话可验证范围 |
| D/E | 按 §0.1 推迟 | 未动 |

**验收**:`pytest` 283 passed(本轮前 261,新增 22 条,均为本轮新功能的直接测试,
无一为迁移适配);`idea run`(裸调用)产出字节路径不变,复核过 recall 计数与此前
一致;`idea run --live --only recall` 真实跑通(hn_algolia 20 条真实结果,
jobs/marketplace/reviews 空 targets 优雅退化)。

**唯一实质性偏离原方案之处**:B3 从"portfolio 直接读 calibrate"改为"pipeline
预计算注入"——这不是偷懒简化,是原方案本身会违反 CI 已经钉死的分层铁律,执行中
发现即改,思路记录在上表,供创始人复核这个改动是否认可。

## §6 不做的事(重申,防止边界回潮)

- 不做拆卡建议、不产实现方案、不给 oc roster 派活——bet memo 到 experiment
  规格为止。
- 不主动读 oc 看板、不拉卡状态——outcome 只收 push。
- 不做数据库、不做用户体系、不做自动部署——文件即状态,纪律同 CLAUDE.md。
- 不在本轮做 MCP server——DMZ 工具扩容够用,意图稳定后再议。
