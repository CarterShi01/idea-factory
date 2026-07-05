# Pipeline v2 改造落地计划(定稿蓝图 → 派工级任务书)

> 状态:2026-07-05 创始人定稿方向,本文档是唯一施工依据。
> 读者:执行具体票的低成本 LLM。**先读完本文 §0–§3,再读你那张票对应的章节,不要只读票。**
> 本文档取代 `docs/research/00-executive-summary-and-roadmap.md` 中与之冲突的部分;研究文档保留作背景。

---

## §0 目标与北极星(为什么改)

**旧目标(废弃)**:每天产出 10–20 条 vetted ideas。
**新北极星**:每周 1 条"带钱证据链、可 48 小时开测"的机会;每月创始人真实冒烟测试 ≥1 次;终极指标是第一笔收入时间。

**三个病根与对应解药(全部落在本计划里):**

| 病根(现网实证) | 解药 | 落在哪 |
|---|---|---|
| 生成侧是规则模板笛卡尔积(「针对X采用工作流嵌入路径」),因子近常数(付费信号全体0.12) | generate 换小模型 LLM 产字段;因子改为作用于 LLM 字段的纯函数 | M2 |
| 评审手里没有真实世界证据 → 人人 50 分待验证,"评委回应"用无证据乐观话术反驳批判 | enrich 取证阶段 + 证据门;diligence 强制分布 + 引证校验 | M1、M3 |
| 没有标签回流 → 权重永远是拍脑袋先验,系统不随时间变准 | 三张日志(ledger)+ retro 对账 + UI 操作即标签 | M0、M5、M6 |

**理念来源**(cheat-on-money):可信度靠机制,不靠内容质量——需求信号从"钱在流动的利益中立源"反推;硬红线宁可错杀;>24 个月信息默认失效;预测→执行→复盘→沉淀闭环。

---

## §1 第一原则与分工铁律(所有票必须遵守)

1. **LLM 成本梯度第一原则**(已写入 CLAUDE.md,那里是权威文本):单条 idea 的 LLM 成本沿漏斗单调递增;便宜的钱早杀,贵的钱只花在上一段幸存者身上;各段总成本(单条×条数)大致持平,某段总成本畸高 = 上一段杀得不够,调漏斗配比,不许降模型档位。
2. **LLM 产字段,代码跑逻辑**:每段的语义判断(抽取/判定/裁决)来自 LLM 输出的结构化字段;每段的逻辑(阈值/排序/闸门/预算/漏斗)是字段上的确定性代码。禁止让 LLM 做算术和排序;禁止用规则模板做语义生成。
3. **隔离规则不变**:`idea_gen`、`idea_eval` 只 import `idea_core`,互不 import;跨半场只通过 `data/processed/ideas.json`。新语义:gen=便宜半场,eval=昂贵半场。
4. **LLM 调用规范**:一律走 `idea_core.llm` 的 batch-first 接口;每个 LLM 步骤一份 `config/llm/<step>.json`(prompt + 输出 JSON schema);每次调用记录 `prompt_version`,响应原文落 trace(见 §4 ledger)。新增 LLM 步骤默认走 `RouterBackend`;涉及 Dify 的现有步骤注意 prompt 锁在 `dify/flows/*.yml`,`config/llm` 只是镜像,两处必须同步改。**绝不允许程序化调用 Claude Code**(CLAUDE.md 硬规则)。
5. **网络纪律**:联网只发生在 recall(--live)与 enrich(--live)且默认关闭;CI 与默认路径永远跑 `data/raw/fixtures/` 离线夹具。给默认路径开 --live 需创始人在会话内明确批准。
6. **每张票的完成标准**:改动最小化;`pip install -e ".[dev]" && idea-gen && idea-eval && pytest` 全绿;新逻辑必须带测试;PR 摘要含 What/Why/How tested/Risks/Follow-up。

---

## §2 新 pipeline 总览(八段一库)

```
profile.json(画像=硬约束,常驻配置)
   │
①recall 多路召回 → ②triage 硬杀闸 → ③generate 候选生成 → ④rank 粗排 ──ideas.json──▶
   (一源一通道)     (红线,宁可错杀)   (小模型,替掉规则模板)  (纯代码因子加权)
                                                              ⑤enrich 尽调取证
                                                                    ↓
                     ⑧retro 复盘回流 ← 创始人执行冒烟测试 ← ⑦portfolio 组合 ← ⑥diligence 裁决
═══ data/ledger/ 三张日志贯穿:impressions / verdicts / outcomes ═══
```

**漏斗量级(周批,设计目标,由仪表盘实测校准):**

| 段 | 入→出(条/周) | 单条LLM相对成本 | 模型档位 |
|---|---|---|---|
| ①recall | 源头→100 | 1x(单次抽取,批量) | 小 |
| ②triage | 100→~30(杀70%) | ~0.5x(语义近重判定) | 小 |
| ③generate | ~30→~40候选(1信号1–2候选) | ~2x(候选成型) | 小-中 |
| ④rank | ~40→10(截断) | 0(复用上游字段) | — |
| ⑤enrich | 10→~6(证据门) | ~15x(联网取证+结构化) | 中 |
| ⑥diligence | ~6→≤3(强制淘汰≥50%) | ~40x(多轮对抗) | 最贵 |
| ⑦portfolio | ≤3→周报Top1–3 | 0 | — |
| ⑧retro | 实测→回流 | ~10x/月 | 中 |

---

## §3 目标目录结构与迁移映射

### 3.1 目标结构

```
src/idea_core/
  models.py          # §4 全部数据类(v2)
  factors.py         # 因子库:作用于 LLM 字段的纯函数(两半共用)
  ledger.py          # 三张日志读写 + run_id/trace 约定
  llm.py             # 现有 batch-first 抽象(不动)
src/idea_gen/
  profile.py         # 画像加载 + 硬约束校验
  recall/
    base.py          # Channel 接口 + 注册表 + 配额
    jobs.py  marketplace.py  reviews.py  inbox.py  hn.py  persona.py
  triage.py
  generate.py        # 保留文件名,实现全换(LLM 后端为默认)
  rank.py            # ranks.py 更名,吸收 score 逻辑
  export.py          # 写 ideas.json + impressions
  pipeline.py / cli.py
src/idea_eval/
  enrich/
    base.py          # Fetcher 接口 + 证据门
    pricing.py  hiring.py  deals.py
  diligence.py       # evaluate.py 演进
  portfolio.py
  retro.py
  export.py          # weekly_report.md + 测试包 + verdicts
  pipeline.py / cli.py
config/
  profile.json  ranking.json  funnel.json(各段配额/淘汰率/预算)
  llm/recall_extract.json  triage_dedup.json  generate_candidates.json
      evidence_structuring.json  diligence_advocate.json  diligence_judge.json
      retro_lesson.json
data/
  raw/fixtures/<channel>.jsonl     # 离线夹具(CI 用)
  ledger/impressions.jsonl  verdicts.jsonl  outcomes.jsonl
  ledger/traces/<run_id>/<stage>.jsonl   # 每次 LLM 调用的 prompt+response
  processed/ideas.json  weekly_report.md  versions/(现有机制沿用)
```

### 3.2 迁移映射(旧→新,执行 M2 时逐条对照)

| 旧 | 新 | 处置 |
|---|---|---|
| collect.py | recall/base.py + 各通道文件 | 拆分;适配器模式/_blank_record/_stable_id 保留复用 |
| normalize.py | recall/base.py 的抽取后处理 | LLM 抽取字段落 Signal;stable id/dedup key 逻辑保留 |
| dedup.py | triage.py 的一部分 | 精确去重保留;语义去重升级为便宜 LLM 判定 |
| generate.py 规则模板路径 | generate.py LLM 路径 | 规则模板降级为 `--backend mock` 测试夹具,不再是默认 |
| ranks.py + score 散逻辑 | rank.py | 合并;MMR/配额打散(14中/6英已修好的逻辑)保留 |
| evaluate.py | diligence.py | 多重下限 kill-gate 保留为 triage 红线的一部分;评审重写 |
| eval/export.py decision_memos | export.py weekly_report | 决策备忘格式重做(§8) |
| (无) | ledger.py / enrich/ / portfolio.py / retro.py / profile.py | 新建 |

---

## §4 数据契约(M0 一次定死,后续票不得擅改)

> 全部为 dataclass(stdlib),序列化 JSON。字段名即契约,改字段=改契约=需创始人点头。

```python
# ---- Signal(①②产物) ----
Signal:
  id: str                    # stable hash(source_channel + raw_ref)
  source_channel: str        # jobs|marketplace|reviews|inbox|hn|persona
  raw_ref: str               # 原始记录定位(url/文件+行号)
  collected_at: date
  event_date: date           # 信号本身的时间(招聘发布日/评论日/成交日)
  # —— LLM 抽取字段(recall_extract 产出)——
  pain_statement: str
  audience: str
  verbatim: str              # 原话引用,不许改写
  money_trace: str           # 钱的痕迹描述:谁在为此付钱/付薪/成交(没有则空串)
  lang: str                  # zh|en
  confidence: str            # real|synthetic
  # —— triage 判定 ——
  status: str                # alive|killed
  killed_by: str|None        # stale_24m|profile_mismatch|exact_dup|semantic_dup|seen_before

# ---- Candidate(③产物,ideas.json 的元素) ----
Candidate:
  id: str
  signal_ids: list[str]
  # —— LLM 生成字段(generate_candidates 产出)——
  title: str
  pain: str
  solution: str              # 具体机制,禁止套话模板
  target_user: str
  why_now: str
  week_mvp: str              # 第1周能做出的最小物
  first_10_customers: str    # 前10个客户的具体触达路径假设
  # —— 代码计算 ——
  factors: dict[str, float]  # factors.py 输出
  alpha: float
  status: str                # ranked_out|awaiting_evidence|in_diligence|killed|test_ready|reported|tested
  evidence_retry: int        # 补证据重试次数(≥2 归档)

# ---- Evidence(⑤产物) ----
Evidence:
  id: str
  candidate_id: str
  kind: str                  # paying_proof|competitor_pricing|reach_path|hiring|deal
  source_url: str
  source_date: date          # 证据自身日期;距今>24月 → valid=False
  fetched_at: datetime
  summary: str               # LLM 结构化(evidence_structuring 产出)
  numbers: dict              # {"price": 29, "currency": "USD", "count": 120, ...}
  valid: bool

# ---- Verdict(⑥产物) ----
Verdict:
  candidate_id: str
  tier: str                  # kill|need_evidence|test_now
  reasons: list[{claim: str, evidence_ids: list[str]}]   # 每条理由必须引证据id,schema强制
  riskiest_assumption: str
  smoke_test: {channel: str, copy_hint: str, price_point: str,
               prediction: {metric: str, target: float, horizon_days: int}} | None  # 仅 test_now
  judge_model: str
  prompt_version: str
  actor: str                 # system|founder(人工推翻时=founder)
  created_at: datetime

# ---- Outcome(⑧输入) ----
Outcome:
  candidate_id: str
  tested_at: date
  prediction: dict           # 从 Verdict.smoke_test.prediction 拷贝
  actual: dict               # 创始人填:{metric: ..., value: ...}
  first_revenue: float|None
  lesson: str                # retro_lesson 产出
```

**三张日志(jsonl,append-only,`idea_core/ledger.py` 统一读写):**

- `impressions.jsonl`:`{run_id, week, stage, entity_id, event: entered|killed|survived, killed_by, ts}` —— 每段进/出/杀都记,漏斗视图与通道存活率全靠它。
- `verdicts.jsonl`:Verdict 全量 + 人工操作事件(`{event: founder_star|founder_kill|founder_override, ...}`)。
- `outcomes.jsonl`:Outcome 全量。
- `traces/<run_id>/<stage>.jsonl`:每次 LLM 调用 `{step, prompt_version, request, response, model, ts}`。

**ideas.json v2**:`{schema_version: 2, run_id, week, profile_hash, candidates: [Candidate...]}`。idea_eval 读到 schema_version≠2 直接报错拒跑(防两半漂移)。

---

## §5 各段实施规格

### ① recall(目标:从"钱在流动的地方"捞信号,宁滥勿缺)

- `recall/base.py`:`Channel` 接口 —— `name`、`quota`(config/funnel.json 里配)、`fetch(since, live: bool) -> list[dict]`(live=False 读 `data/raw/fixtures/<name>.jsonl`)。注册表 dict,加源=加一个文件+注册一行。
- 通道优先级(M2 先做前 4 个,live 适配 M3+ 逐个补):
  1. `jobs.py` — 招聘信号(公司为痛点付薪=最强付费证据)。fixture 先行;live 版抓 RSS/公开列表页,**不碰需授权 API**。
  2. `marketplace.py` — 服务成交信号(Upwork/Fiverr/闲鱼类目)。
  3. `reviews.py` — 竞品 1–3 星评论(已付费用户的不满)。
  4. `inbox.py` — 创始人 inbox.jsonl(现有,平移)。
  5. `hn.py` — 现有 HN 通道降配额(它是"有趣"信号不是"付钱"信号)。
  6. `persona.py` — **降级:默认配额 0,不产 idea**;仅创始人显式 `--channel persona` 时启用;其角色移到 ⑥ 做目标用户压力测试(见 ⑥)。
- LLM 步骤 `recall_extract`:小模型,批量;输入原始记录,输出 Signal 的 LLM 字段(schema 见 §4)。`verbatim` 必须是原文摘句;`money_trace` 抽不出就留空(留空的信号在②会吃低优先,但不硬杀)。
- 指标:各通道最终存活率(周报尾部附一行)。

### ② triage(目标:硬杀,省下后面所有钱)

红线全部是**代码**,按序执行,任一命中即 `killed_by` 落日志:
1. `stale_24m`:`event_date` 距今 >24 个月(cheat-on-money 时效规则;取代温柔指数衰减作为生死线;衰减仍留在④rank 里作排序用)。
2. `profile_mismatch`:与 `config/profile.json` 硬冲突(预算上限、一人无法交付的形态清单、语言/合规禁区)。profile.json 由 M0 定 schema,创始人填值。
3. `exact_dup`:现有 dedup_key 逻辑。
4. `semantic_dup`:LLM 步骤 `triage_dedup`(小模型,批量):候选 pair 判定 same/different,pair 由代码用便宜启发式预筛(同通道+词面相似)后送判,控制调用量。
5. `seen_before`:查 ledger 历史(含往周已杀/已报告的)。
- 指标:杀率(目标~70%)+ 每周随机抽 5 条被杀信号进周报"误杀审计"栏,创始人扫一眼。

### ③ generate(目标:替掉规则模板,候选成型)

- LLM 步骤 `generate_candidates`:小-中模型;输入 = 幸存 Signal(全字段)+ profile 摘要;输出 1–2 个 Candidate 的 LLM 字段。
- prompt 硬要求(写进 config/llm/generate_candidates.json):`solution` 禁止出现"工作流嵌入/决策辅助/数据对账"式万能模板句;`first_10_customers` 必须具体到"哪个群/论坛/名单";`why_now` 必须引用 signal 的 event_date 或 money_trace。
- 旧规则模板保留为 `--generate-backend mock`,只供离线 CI。
- 代码逻辑:schema 校验失败自动重试 1 次,再失败丢弃该信号并落日志。

### ④ rank(目标:决定谁配进昂贵半场;纯代码)

- `factors.py` 重写为作用于 Candidate/Signal 字段的纯函数,只保留**可从字段落地计算**的因子:`money_trace_strength`(money_trace 非空+含数字加分)、`freshness`(event_date 衰减)、`profile_fit`(与 profile 技能/渠道清单的匹配计数)、`audience_reachability`(first_10_customers 是否具体)、`novelty`(与 ledger 历史的距离)。删除无法落地的拍脑袋因子。
- 权重在 `config/ranking.json`;截断 Top-K(config/funnel.json,默认 10);MMR/语言配额打散逻辑平移保留。
- 落 ideas.json + impressions。

### ⑤ enrich(目标:给幸存者配齐钱证据链;--live 才联网)

- `enrich/base.py`:`Fetcher` 接口 `fetch(candidate, live) -> list[Evidence]`;live=False 读 fixture。三个 fetcher:
  - `pricing.py`:按 candidate 关键词搜竞品定价页,抓价格与方案名。
  - `hiring.py`:相关岗位招聘量与薪资。
  - `deals.py`:服务市场同类成交(单价、销量)。
- LLM 步骤 `evidence_structuring`:中模型;输入抓回的页面文本,输出 Evidence 的 summary/numbers/source_date。
- **证据门(代码)**:放行进⑥需同时满足 ①≥1 条 `paying_proof`(hiring/deal/竞品收入任一,valid=True)②≥1 条 `competitor_pricing`(有名字有价格)③ `reach_path` 成立(first_10_customers 被至少 1 条证据支持或创始人渠道清单覆盖)。缺任一 → `awaiting_evidence`,下周自动重试;`evidence_retry ≥ 2` → 归档,落日志。
- 预算护栏:config/funnel.json 里 `enrich_max_fetch_per_candidate`、`enrich_weekly_budget`;超了就停并在周报标注"本周取证配额用尽,漏掉 N 条"——**不许静默截断**。

### ⑥ diligence(目标:拿证据开庭,敢杀)

- 两个 LLM 步骤,**模型/prompt 与③生成侧不同**(反自我偏好):
  1. `diligence_advocate`(devil's advocate):输入 candidate+全部 Evidence,输出致命质疑列表,每条必须引 evidence_id 或标注 `no_evidence_available`。
  2. `diligence_judge`:输入 candidate+Evidence+质疑列表,输出 Verdict。schema 强制 `reasons[].evidence_ids` 非空——**引不出证据的反驳无效,该质疑自动成立**(代码校验,不合格重试 1 次,再不合格该候选直接 need_evidence)。
- persona 压力测试(可选子步骤,M4+):对 test_now 候选,用人群池 persona 各出一条"我为什么不会买",附进周报,不改变 tier。
- **强制分布(代码)**:每批 `kill + need_evidence ≥ 50%`;若 judge 给的 test_now 过多,按 judge 置信度降序保留至多 `ceil(n/2)`,其余降为 need_evidence,并在日志标 `forced_downgrade`(这个标记本身是校准信号)。
- 废除 0–100 分与"评委回应"环节。tier 三档就是全部输出。
- 指标:tier 分布(不许单档>80%)、与 outcome 的事后一致率。

### ⑦ portfolio(目标:周报 Top1–3,每条带 48h 测试包;纯代码)

- 已投递过滤:与 ledger 历史 reported 候选去重(语义近重用④的 novelty 因子阈值)。
- 打散:沿用现有配额逻辑,维度改为"人群×渠道"不许重叠。
- `weekly_report.md` 每条格式见 §8;测试包字段直接取 Verdict.smoke_test。
- 指标:周报采纳率(创始人实际开测数/推荐数)。

### ⑧ retro(目标:系统随时间变准)

- CLI:`idea-eval retro --candidate <id> --metric signups --actual 7 [--first-revenue 99]` → 写 Outcome。
- LLM 步骤 `retro_lesson`:中模型,输入 prediction vs actual + 该候选全 trace,输出 lesson(一句话,存 outcomes)。
- 校准 v1(M5):只出报告不自动调权——`idea-eval stats` 输出:各通道存活率、triage 杀率、tier 分布、预测误差表、各因子与 outcome 的相关性。创始人看报告手调 config/ranking.json。自动调权是 v2,不在本计划。

---

## §6 里程碑与票(按序执行,每票一个 PR)

> 每票自带 DoD(Definition of Done)。**票内列出的"禁止"是硬边界,遇到想越界的情况停下来问,不许自作主张扩 scope。**

### M0 契约层(1 周,无行为变化)
- **T0.1** `idea_core/models.py` v2:§4 全部 dataclass + (de)serialize + schema_version。旧类保留别名,标 Deprecated。DoD:pytest 覆盖 round-trip;现有 pipeline 不破。
- **T0.2** `idea_core/ledger.py`:三日志 append/read + run_id 生成 + traces 目录约定。DoD:并发 append 安全(文件锁或单进程约定注释);单测。
- **T0.3** `config/profile.json`、`config/funnel.json`、`config/ranking.json` schema + 校验函数 + 示例值。DoD:非法配置启动即报错。
- **T0.4** `config/llm/` 七个步骤文件骨架(prompt 占位 + 输出 schema 定稿)。DoD:schema 与 §4 字段一一对应。禁止:此票不写 prompt 正文。

### M1 止血:diligence 重做(1 周,最大 ROI,先于 gen 侧改造)
- **T1.1** `diligence.py`:两步 LLM(advocate/judge)+ 引证校验 + 强制分布 + 三档 tier;读现有 ideas.json(v1 兼容垫片)。DoD:同一批 50 条输入,tier 分布三档皆非零;每条 reason 都带 evidence_ids 或 no_evidence_available;mock 后端下 pytest 可复现。
- **T1.2** 废除 0–100 分与评委回应;decision_memos.md 换 §8 新格式。DoD:输出无"待验证 50/100"字样;无"评委回应"栏。
- **T1.3** verdicts.jsonl 落日志 + prompt_version 进 trace。
- 注:此时还没有 enrich,advocate 会大量输出 no_evidence_available——**这是预期行为**,它会把几乎所有候选压进 need_evidence,正好证明证据门的必要性,周报会难看两周,接受。

### M2 便宜半场重构(2 周)
- **T2.1** `recall/base.py` + 现有三源迁入通道(inbox/hn/persona),fixtures 落位,persona 配额=0。DoD:`idea-gen` 离线跑通,产出 Signal v2。
- **T2.2** `recall_extract` LLM 步骤接入(router 后端,mock 供 CI)。DoD:verbatim 为原文摘句(测试:字段是输入子串)。
- **T2.3** `triage.py` 五条红线 + impressions 落日志 + 误杀审计抽样。DoD:每条被杀信号有 killed_by;杀率可从日志算出。
- **T2.4** `generate.py` LLM 化 + 模板禁令 + mock 降级。DoD:默认后端下输出不含模板句(测试:黑名单短语断言);每信号 1–2 候选。
- **T2.5** `rank.py` 合并 + factors.py 重写(§5④的因子清单)+ ideas.json v2。DoD:因子对构造样例的单测;打散配额行为与现网一致。
- **T2.6** 新通道 fixture 版:jobs/marketplace/reviews(各 20 条合成夹具,格式仿真实源)。禁止:此票不写 live 抓取。

### M3 enrich + 证据门(2 周,--live 首次引入,默认关)
- **T3.1** `enrich/base.py` + 证据门 + awaiting_evidence 回流队列 + 预算护栏。DoD:fixture 证据下,缺证据候选正确进队并在下轮重试,retry≥2 归档。
- **T3.2** `evidence_structuring` LLM 步骤 + Evidence 落库 + 24 月 valid 判定。
- **T3.3** 三个 fetcher 的 live 版(urllib,stdlib;每 fetcher 独立开关;失败降级为空列表并落日志,不许抛死 pipeline)。DoD:--live 冒烟由创始人手跑验收;CI 不联网。**禁止:抓需登录/授权的 API;禁止把 --live 设为默认。**
- **T3.4** diligence 去掉 v1 垫片,只吃带 Evidence 的输入;recall 的 jobs/marketplace/reviews live 版同规格补齐。

### M4 portfolio + 周报(1 周)
- **T4.1** `portfolio.py`:已投递过滤 + 人群×渠道打散 + Top≤3。
- **T4.2** `export.py`:weekly_report.md(§8 格式)+ 48h 测试包 + 通道存活率/误杀审计附录。DoD:报告里每条 idea 的每个证据是可点击链接。
- **T4.3** persona 压力测试子步骤(可选段,配额受 funnel.json 控制)。

### M5 retro + 仪表盘(1 周)
- **T5.1** `retro.py` + retro CLI + outcomes 落库 + retro_lesson。
- **T5.2** `idea-eval stats`:§5⑧ 列的全部指标,读三张日志纯代码计算,输出 markdown。DoD:对构造日志的单测给出确定数字。

### M6 UI 对齐(1–2 周,基于现有 WebUI;数据全部来自 ledger 文件,禁止引入数据库服务)
- **T6.1** 漏斗视图:每 run 一行,各段进/出/杀 + 通道存活率(读 impressions)。
- **T6.2** 单 idea 全链路 trace 视图:signal 原文 → 各段字段 → killed_by → 证据链接 → verdict 全文 → 每次 LLM prompt+response(读 traces)。DoD:任一条 idea"为什么排第一/为什么被杀"30 秒内可答。
- **T6.3** 人工操作=标签:⭐看中/杀/推翻 tier/填 outcome,全部写 verdicts/outcomes(actor=founder)。DoD:UI 每个操作在 jsonl 里有对应事件。
- **T6.4** what-if 单段重跑:选一条 idea + 一段,改字段或 prompt_version 后只重跑该段,结果并排 diff,不落正式日志(落 `traces/whatif/`)。
- 注:WebUI 部署拓扑不变(北京机只 serve,数据 scp 同步);**本里程碑不改运行栈、不加服务**——越界即停,问创始人。

---

## §7 需要创始人点头的事项清单(执行中遇到就停)

1. 任何 --live 默认开启、或给 CI/定时任务开网络。
2. profile.json 的具体取值(预算、技能、渠道清单)——M0 出 schema 后创始人亲自填。
3. 新增付费数据源或需授权的 API。
4. 删除/重命名 data/processed、data/ledger 下任何历史数据。
5. Dify flows 的改动(prompt 镜像不变式,牵涉部署拓扑)。
6. 里程碑顺序调整或任何本文档未列的 scope。

## §8 周报单条格式(portfolio 出口,验收样板)

```markdown
## 本周 #1:<title>            tier: 本周就测
**痛点**:<pain>(源:<channel>,<event_date>,[原话](raw_ref))
**方案**:<solution>
**钱的证据链**:
- [竞品X定价页](url) $29/mo,3档方案(2026-05 抓取)
- [BOSS 相关岗位](url) 近30天 17 个,median ¥25k(2026-06)
- [闲鱼同类服务](url) 成交 240 单,均价 ¥45
**前10个客户在哪**:<first_10_customers>
**最危险假设**:<riskiest_assumption>
**48h 测试包**:渠道=<channel>;文案要点=<copy_hint>;定价=<price_point>;
  预测=<horizon_days>天内 <metric> ≥ <target>(测完跑 `idea-eval retro ...` 回填)
**评委理由**(每条带证据编号):...
**人群反对声**(persona 压力测试,仅供参考):...
```

**全局验收(整个计划完成的标志)**:连续 2 周,周报 ≤3 条且每条证据链完整可点击;tier 分布无单档>80%;创始人完成 ≥1 次真实冒烟测试并回填 outcome;`idea-eval stats` 能给出第一版预测误差表。

---

## §9 实施状态(2026-07-05 首轮落地记录)

> 本节记录本轮实际写了什么、和写这份计划时对现网代码的假设有什么出入、以及故意
> 没做的部分为什么没做。后续接手的人(人或 LLM)先看这节,再决定下一票怎么开。

### 9.1 与原计划的核心出入:现网比计划假设的成熟得多

写 §0–§8 时,是把当时看到的产出(`ideas.md`/`decision_memos.md` 里模板化的
"针对X采用Y路径"、评委全员 50/100)当成整个系统的技术水位来推的,据此把 M0–M2
设计成"从规则模板重建生成侧、从零建评审"。**动工前重新通读现网代码后发现假设有误**:

- `idea_gen/generate.py` 早就有 `generate_llm`(config 驱动、per-source 分叉、
  跨源融合、Verbalized-Sampling 式候选内去重)——只是**默认后端仍是 `rule`**,规则
  模板路径没被替换,产线上跑的是弱路径,不代表 LLM 路径不存在。
- `idea_eval/evaluate.py` 早就有 devil's-advocate 式 `critique_survivors` +
  反谄媚 `judge_survivors`(生成/评审用不同模型、低置信度自动降级到 review、
  五维自洽性校验)+ `diversify_select` 打散——三档裁决(pursue/review/kill)
  本质上已经是 §2 说的 test_now/need_evidence/kill,不需要重新发明。
- `founder.json` + `render_founder_block` + `founder_fit` 因子早就把"创始人画像"
  注入每个 LLM 步骤——§2/§5 设想的"画像=硬约束"缺的只是**硬门**(软因子之外的
  显式 anti-fit 判定),不是画像本身。
- `versioning.py`(不可变版本快照)、`config/funnel.json`(漏斗切分量可配置)
  已经就位。

**结论**:全员 50/100、模板化产出的病根不是"缺 LLM 化",而是①默认后端仍走规则
路径 ②评委手里从来没有真实世界证据 ③没有标签回流(见 CLAUDE.md 第一条设计原则
和创始人对话记录)。本轮据此把施工范围收敛为**在现有成熟核心上叠加缺的三块**:
证据(enrich)、硬红线(triage)、标签回流(ledger + retro),而不是重写 gen/eval。

### 9.2 已落地(全部 opt-in,默认路径字节级不变)

| 模块 | 文件 | 对应计划章节 |
|---|---|---|
| 三张日志 + trace | `src/idea_core/ledger.py` | §4 |
| Evidence / Outcome 数据类 | `src/idea_core/models.py`(新增,不改旧字段) | §4 |
| 硬红线(信号>24月过期、候选显式 anti-fit) | `src/idea_gen/triage.py`,新增 `factors.has_hard_anti_fit` | §5②；`idea-gen --use-triage` |
| 尽调取证 + 证据门(fixture-backed) | `src/idea_eval/enrich.py` + `data/raw/fixtures/evidence/{pricing,hiring,deals}.jsonl` | §5④ |
| 证据感知裁决(引证/强制分布) | `evaluate.py` 新增 `apply_evidence`/`enforce_evidence_grounding`/`enforce_forced_distribution` | §5⑤；`idea-eval --require-evidence` |
| 复盘回流 | `src/idea_eval/retro.py` + `idea-eval retro` CLI | §5⑧ |
| 只读统计 | `src/idea_eval/stats.py` + `idea-eval stats` CLI | §6 M5 |
| 周报(§8 格式) | `export.write_weekly_report`,`require_evidence=True` 时才写 | §7/§8 |
| 三个新召回源(钱在流动的地方) | `src/idea_gen/sources/{jobs,marketplace,reviews}.py` + `data/raw/fixtures/{jobs,marketplace,reviews}.jsonl`,默认启用(纯离线 fixture,不算联网) | §5① |
| CLI 开关 | `idea-gen --use-triage`;`idea-eval --require-evidence/--evidence-data-dir/--evidence-live/--max-pursue-frac`;`idea-eval retro ...`;`idea-eval stats` | — |

**验收**:测试从 145(改动前基线)增至 190,全绿;真实 `idea-gen --use-triage &&
idea-eval --require-evidence && idea-eval stats && idea-eval retro ...` 在仓库
真实 `data/` 上跑通全链路(见 2026-07-05 session 记录:triage 杀 6 条过期信号 + 6
条 anti-fit 候选,证据门筛出 3 条周报,retro 回填后 stats 出预测误差)。

### 9.3 明确推迟(需要创始人点头或是后续票,不是漏做)

- **enrich 的三个 fetcher 和三个新召回源的 `live=True` 路径**:目前都是"返回
  `[]`"的桩函数。接真实网络(竞品定价页/招聘网站/服务市场/评论页)属于 CLAUDE.md
  硬规则"不经批准不得给默认管线加真实外部 API 调用"——接口、证据门、fixture 全部
  就位,接线是纯粹的"填一个函数体"级别的后续票。
- **`evidence_structuring` LLM 步骤**:计划设想抓回来的网页原文要经一次 LLM
  结构化。本轮 fixture 本身就是"已结构化"的桩数据,所以没接这一步;真正接 live
  fetcher 时才需要。
- **judge 自己的输出里强制引用 `evidence_ids`**:本轮的证据强制是**裁决之后的
  确定性闸门**(`enforce_evidence_grounding`:没证据的 pursue 一律降级),而不是
  改 `config/llm/judge.json` 的 schema 逼 LLM 自己在输出里点名证据编号。这样做
  是为了不动 Dify 的 prompt-lock 不变式(改 judge 的 prompt/schema 要同步改
  `dify/flows/judge.yml`,是更大的改动面)。效果上达到了"没证据不能过"的目标,
  但没有达到"评委的反驳必须引用证据"这条更强的版本——留作下一票。
- **generate 的默认后端没有从 `rule` 切到 LLM**:`--gen-backend` 早就支持
  `router`/`cc`/`dify`,只是 CLI 默认值仍是 `rule`。切默认值会改变离线 demo 的
  产出内容和成本模型,按计划 §7 的精神,这类默认行为变更留给创始人拍板,不在本轮
  自动切换。
- **人群压力测试子步骤**(⑥ diligence 的"人群反对声")、**retro_lesson 的 LLM
  提炼**(目前 lesson 是创始人手打的自由文本,零 token)、**用 outcomes 自动回调
  因子权重**(目前 `idea-eval stats` 只出数字,不自动调 `config/ranking.json` 一类
  的权重——因为压根还没有 `ranking.json`,现网权重在 `ranks.DEFAULT_WEIGHTS` +
  `config/funnel.json` 里,自动回调是要设计一个新配置面的独立工作)。
- **Studio/WebUI(M6 的四个视图)**:一个字节没动。ledger 的数据模型(trace 按
  run_id/stage 分文件、verdicts/outcomes 按 append-only jsonl)是按"UI 直接读
  这些文件渲染"设计的,但漏斗视图/单 idea 全链路 trace/人工操作即标签/单段
  what-if 重跑这四个界面本身完全没有实现,是独立的一票(或几票)。
- **Signal 上没加 `money_trace` 字段**:计划 §4 的 Signal 契约里设想了一个专门
  的 `money_trace` 字段。本轮为了不再扩大共享契约的改动面,新召回源的"钱证据"
  直接写进了 `pain`/`text` 的自然语言里(现有 `pain_intensity`/`payment_signal`
  因子本来就扫这些字段里的付费词表,效果等价),没有新增字段。

### 9.4 本地开发环境的一个旁支发现(非代码问题)

会话开始时 `pip show idea-factory` 指向的可编辑安装路径(`~/workspace/idea-factory`)
已不存在(仓库被移到了 `oc-hands-workspace/idea-factory`),导致 `idea-gen`/
`idea-eval` 控制台脚本报 `ModuleNotFoundError`。本轮把 site-packages 里那个
`.pth` 文件指向改到当前仓库路径以便跑通端到端冒烟测试——这是本机开发环境的修复,
不是仓库改动,后续如果换机器/换用户可能要重新 `pip install -e ".[dev]"`。
