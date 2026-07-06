---
doc: research-brief
title: "Reference Scan 任务书：10-lane 并行调研八段架构下可参考的开源项目"
date: 2026-07-06
status: approved（创始人 2026-07-06 拍板：另一 session 拉取本文档，10 subagent 并行执行）
related: [../00-executive-summary-and-roadmap.md, ../../design/pipeline-v2-plan.md]
---

# Reference Scan 任务书（自包含：只读本文即可开工）

> **给执行者（另一个 Claude 会话）的一句话**：你要派 10 个并行 subagent，各自调研一个
> lane 的 GitHub 热门高价值开源项目，按 §5 的统一格式各写一份报告到本目录，最后由你
> 汇合成 `00-summary.md`。全程只读调研（WebSearch/WebFetch/读本仓库），**不改 src/、
> 不装依赖、不跑任何被调研项目的代码**。

---

## §1 背景：为什么做这次扫描

**idea-factory 的使命与北极星**：把三路信号（外部事件、创始人 inbox、模拟人群痛点）
变成**每周 1 条"带钱证据链、48 小时可开测"的机会**；终极指标是第一笔收入时间。
设计蓝图见 `docs/design/pipeline-v2-plan.md`（唯一施工依据），背景研究见
`docs/research/00-executive-summary-and-roadmap.md`。

**这次扫描的目的**：创始人要给 idea-factory 移植一套"reference-miner"机制（原型在
one-creator 仓库）——为每个 pipeline 阶段登记若干开源参考源（`sources.yaml` 注册表 +
钉 commit 镜像 + per-source 挖矿 skill），持续从开源生态吸取经验优化各模块。本次扫描
是这套机制的**第 0 步：为每个阶段找出值得登记的候选源**。

**第一原则（评估候选时必须对齐）——LLM 成本梯度**：每段的语义判断来自 LLM 产出的
结构化字段，每段的逻辑是字段上的确定性代码；单条 idea 的 LLM 成本沿漏斗单调递增，
便宜的钱早杀、贵的钱只花在幸存者上。一个候选项目如果诱导"让 LLM 做排序/算术"或
"在便宜段用贵模型"，要在报告里标记这个冲突。

---

## §2 目标架构：八段 + 两横切（调研的落点语义）

> 注意：仓库目录重构正在进行中，当前物理文件名（collect/normalize/dedup/ranks/
> evaluate）与八段命名尚未一一对应。**调研以下面的八段语义为落点**，"当前代码落点"
> 列仅供定位现状。

| 段 | 不变使命 | 当前代码落点 |
|---|---|---|
| ①recall | 从"钱在流动的地方"捞信号，宁滥勿缺 | `src/idea_gen/collect.py` + `sources/`（registry 模式，8 个 adapter）+ `normalize.py` |
| ②triage | 便宜地硬杀（>24 月过期、画像硬冲突、精确/语义重复），省下后面所有钱 | `src/idea_gen/triage.py` + `dedup.py` |
| ③generate | 幸存信号 → 成型候选（具体机制，禁模板套话） | `src/idea_gen/generate.py`（规则+LLM+跨源融合） |
| ④rank | 纯代码因子加权，决定谁配进昂贵半场 | `src/idea_gen/ranks.py` + `src/idea_core/factors.py` |
| ⑤enrich | 给幸存者配齐钱证据链（竞品定价/招聘/成交），证据门放行 | `src/idea_eval/enrich.py`（Fetcher 协议，live 为桩） |
| ⑥diligence | 拿证据开庭：devil's advocate + judge，引证强制、敢杀 | `src/idea_eval/evaluate.py`（critique/judge/enforce） |
| ⑦portfolio | 组合成周报 Top≤3 + 48h 测试包，人群×渠道打散 | `evaluate.py` 的 diversify_select + `export.py` |
| ⑧retro | 预测 vs 实际回流，系统随时间变准 | `src/idea_eval/{retro,stats,calibrate}.py` |
| 横切 A | LLM 基建：batch-first 抽象、多后端、prompt+schema 配置化、trace | `src/idea_core/llm.py` + `config/llm/*.json` |
| 横切 B | 可观测与标签：三张 append-only ledger、漏斗视图、UI 操作即标签 | `src/idea_core/ledger.py` + `studio/` |

架构铁律（评估"能不能借"时的过滤器）：
- `idea_gen` 与 `idea_eval` 互不 import，只经 `data/processed/ideas.json` 通信；
- **当前阶段纯标准库**（stdlib-only），新依赖需创始人单独批准；
- 默认路径**离线**，联网是 opt-in；
- 绝不程序化调用 Claude Code。

---

## §3 调研纪律

### 3.1 评估维度（每个候选都要给出）

| 维度 | 怎么看 |
|---|---|
| 热度/权威 | stars、被谁背书（官方/大厂/知名个人） |
| 活跃度 | 近 6 个月 commit/release/issue 响应；单作者停更要标记 |
| license | MIT/Apache 优先；**GPL/AGPL/非商用（NC）必须显著标记**（影响能不能抄代码 vs 只能借概念） |
| 依赖重量 | 能否"只挖不跑"（读源码/prompt/schema 就能借）；要跑起来才有价值的重型框架降级 |
| 可挖性 | 有没有可直接借的具体资产：prompt 文本、JSON schema、算法实现、评估 rubric、数据格式 |
| 中国市场相关性 | 仅对 recall/portfolio 等面向中文信号源的 lane 加分项 |

### 3.2 硬约束（违反即降为 concepts-borrow 或 skip）

- **glue-only**：我们不 vendor 重型框架运行时；优先"借模式/借 prompt/借 schema"，
  其次"抄一个纯函数"，最后才是"引一个依赖"（需创始人批准）。
- **只挖不跑**：调研阶段绝不 clone 后执行被调研项目的代码；读 GitHub 页面、README、
  源码文件即可。
- **诱导违反成本梯度的**（如全量数据上贵模型逐条打分）：标记冲突，说明裁剪方式。

### 3.3 SKIP / REJECT 也是交付物

评估过但不推荐的项目**必须记录**：id + 一句话理由（如"154 个浅模板堆无方法论"、
"provider 锁定"、"AGPL"、"停更 2 年"）。这是防止未来重复爬坑的负面清单，价值不低于
推荐清单。

---

## §4 十个 lane（每 lane = 1 个并行 subagent）

每个 lane 的任务：**找 5–10 个候选 → 按 §3 评估 → 给出 Top 2–3 推荐（含挖什么/怎么
裁剪）+ skip 清单**。种子候选只是起步线索，需要验证现状（stars/活跃度会变），并主动
扩展搜索（GitHub topic、awesome-list、"X alternative"检索）。

### L1 recall：信号采集（钱在流动的源头）
- **要回答**：招聘信号（岗位=公司为痛点付薪）、服务市场成交、竞品差评（1–3 星）、
  中文社区（小红书/闲鱼/BOSS/知乎）、HN/GitHub 趋势——各有哪些成熟采集项目？
  哪些提供"挂已登录浏览器只读公开页"的合规抓取模式？增量监测（页面变化检测）有什么可借？
- **种子**：RSSHub（万物皆 RSS，含大量中文源）、NanmiCoder/MediaCrawler（小红书/抖音/
  快手爬虫）、JobSpy（多站招聘聚合）、changedetection.io（页面变化监测）、GHArchive/
  gharchive 分析类、maxdorninger 或同类 job-scraper、app 评论抓取（google-play-scraper /
  app-store-scraper）。
- **落点**：`idea_gen/sources/` 新 adapter 的实现模式与目标站点清单（数据面：fixture
  格式与字段设计也算）。

### L2 triage：去重与硬过滤
- **要回答**：文本精确/近重去重的工业级做法（MinHash/SimHash/LSH）哪家实现最干净、
  能否抄成纯 stdlib 函数？语义去重的"便宜 LLM pair 判定 + 启发式预筛"有没有现成范式？
  规则红线引擎（宁可错杀）有什么可借的表达方式？
- **种子**：ChenghaoMou/text-dedup、ekzhu/datasketch（MinHash LSH）、MinishLab/semhash、
  seatgeek/thefuzz、simhash 各实现。
- **落点**：`idea_gen/triage.py` + dedup 逻辑（机制面为主：算法与阈值设计）。

### L3 generate：LLM 想法/假设生成
- **要回答**：自动化科研/创意生成系统（想法过量产出→筛选）的 prompt 架构长什么样？
  怎么防模板化套话（我们已用 Verbalized Sampling）？信号→商业点子的成型 prompt 有无
  高质量开源范例？多样性采样与候选内去重的范式？
- **种子**：SakanaAI/AI-Scientist（及 v2）、AI-Researcher 类项目、GenSpark/ideation
  agent 类、结构化 brainstorm prompt 库、arXiv 上 hypothesis-generation 配套代码仓。
- **落点**：`config/llm/generate.json` 的 prompt 与 schema（数据面）+ 生成侧流程（机制面）。

### L4 rank：排序、因子库与多级漏斗
- **要回答**：推荐系统"召回→粗排→精排→重排"的开源实现里，配额打散/MMR/多目标融合
  怎么做得干净？量化因子库（因子=纯函数、单一真相源、防漂移）的工程范式可借什么？
  我们的 founder_fit 复合因子有没有同构先例（个性化 boost）？
- **种子**：microsoft/qlib（因子/alpha 库工程）、freqtrade（策略-回测同源，本项目
  已借过教训）、gorse-io/gorse、recommenders-team/recommenders、MMR/DPP 的独立实现。
- **落点**：`idea_core/factors.py` + `idea_gen/ranks.py` + `config/funnel.json`（机制面为主）。

### L5 enrich：取证研究 agent 与网页抓取
- **要回答**：deep-research 类 agent（检索→抓取→结构化证据）的流程拆解，哪些环节能
  裁剪成我们的 Fetcher（竞品定价页/招聘量/成交数据）？抓取层（反爬/渲染/转 markdown）
  哪家最适合"低频、少量、合规"的取证场景？证据结构化（页面→带数字的 Evidence）的
  prompt/schema 范式？
- **种子**：assafelovic/gpt-researcher、dzhng/deep-research、HKUDS 或 langchain 系
  open-deep-research、unclecode/crawl4ai、firecrawl（注意 license 与云绑定）、
  searxng/searxng（自托管元搜索）。
- **落点**：`idea_eval/enrich.py` 三个 fetcher 的 live 实现路径 + `evidence_structuring`
  步骤（机制面 + 数据面 prompt）。

### L6 diligence：LLM-as-judge 与对抗评审
- **要回答**：LLM 评审的可靠性工程（反谄媚、位置偏差、自我偏好、置信度校准）业界
  怎么做？多智能体辩论/法庭范式（advocate vs judge）有哪些可借的 prompt 与流程？
  "引证强制"（评审理由必须引 evidence id，引不出则质疑自动成立）有没有先例？
  评审 rubric 的 schema 设计？
- **种子**：promptfoo/promptfoo、confident-ai/deepeval、openai/evals、G-Eval/JudgeLM/
  PandaLM 论文配套仓、ChatEval / Multi-Agent-Debate（MAD）类、LLM-as-a-judge
  survey 附带资源列表。
- **落点**：`config/llm/{critique,judge}.json` prompt 与 schema（数据面）+ enforce
  逻辑（机制面）。**注意**：prompt 正文锁在 `dify/flows/*.yml`，config/llm 是镜像，
  两处必须同步——推荐改 prompt 的候选要提醒这条不变式。

### L7 portfolio：组合选择与周报生成
- **要回答**：从"Top-N 列表"到"一个组合"（人群×渠道不重叠、单一主题设上限）有什么
  可借的选择算法（DPP/子模优化/配额法）？自动周报/digest 生成（markdown 报告、证据
  链接可点击、附录漏斗指标）有什么好范式？已投递去重（跨周历史）怎么做？
- **种子**：DPP/submodular 选择的轻量实现、静态报告生成器（自动 changelog/digest 类
  工具）、投资组合构建的开源方法论仓、newsletter 自动化项目。
- **落点**：diversify/portfolio 逻辑 + `export.py` 周报格式（机制面为主）。

### L8 retro：校准、回测与实验记录
- **要回答**：预测校准（Brier score、校准曲线、预测区间）的轻量实现？"预测→实际→
  教训"回流闭环有没有开源先例（forecasting 社区工具、决策日志）？轻量实验追踪
  （不引数据库服务、文件即真相）可借什么？因子权重的安全自动调参（样本不足明确拒绝）
  范式？
- **种子**：Metaculus 生态工具、properscoring 类库、fortuna/校准库、mlflow（太重，
  借概念）、aim/轻量 tracker、量化回测框架的 walk-forward 校准部分。
- **落点**：`idea_eval/{retro,stats,calibrate}.py` + ledger 消费（机制面）。

### L9 横切 A：LLM 基建（batch、结构化输出、prompt 管理）
- **要回答**：多后端路由与降级（我们已有 Router/CC-handoff/Mock/Dify 四后端）业界
  最佳实践还有什么可补？结构化输出强制（schema 校验、失败重试、修复）哪家的**模式**
  值得抄成 stdlib 实现？prompt 版本管理与 A/B（我们已有 prompt_version 进 trace）
  可借什么？batch API 的成本优化范式？
- **种子**：BerriAI/litellm（借路由/重试模式，不引依赖）、567-labs/instructor、
  dottxt-ai/outlines、BoundaryML/baml、microsoft/prompty、prompt 管理类
  （langfuse prompts / promptlayer 的开源部分）。
- **落点**：`idea_core/llm.py` + `config/llm/` 约定（机制面；一律"借模式抄纯函数"，
  stdlib 铁律下基本不可能引这些依赖本身）。

### L10 横切 B：可观测、trace 与"操作即标签"
- **要回答**：LLM trace/漏斗可观测的开源产品（langfuse/phoenix/opik）的**数据模型**
  （trace/span/score 的 schema、人工标注事件怎么记）可借什么到我们的三张 jsonl ledger？
  数据标注工具（argilla/Label Studio）的"UI 操作写回标签"交互与存储范式？
  轻量漏斗仪表盘（读文件、无数据库）有没有先例？
- **种子**：langfuse/langfuse、Arize-ai/phoenix、comet-ml/opik、argilla-io/argilla、
  HumanSignal/label-studio、observability schema 标准（OpenTelemetry GenAI 语义约定）。
- **落点**：`idea_core/ledger.py` schema 演进 + `studio/`（机制面为主；注意非目标：
  不引数据库服务，ledger 文件即真相）。

---

## §5 统一产出格式（严格遵守，便于机器汇合）

每个 lane 写一个文件：`docs/research/reference-scan/L<N>-<slug>.md`
（如 `L1-recall-signal-mining.md`）。结构：

```markdown
---
doc: research
lane: L<N>
title: "<lane 名>"
date: <执行日期>
agent: subagent
---

# L<N> <lane 名>

## 结论速览
<Top 2–3 推荐一句话 + 最重要的一个发现>

## 推荐候选（Top 2–3，按价值排序）

### <id>（kebab-case，如 gpt-researcher）
- repository: github.com/<org>/<repo>
- stars: ~Nk · license: <SPDX> · 活跃度: <近6月概况；单作者/停更要写明>
- mined_for:
  - 数据面: <可直接 promote 的资产：prompt/schema/fixture格式/因子定义/…；没有则写 无>
  - 机制面: <值得提案改我们代码的模式/算法；没有则写 无>
- 挖什么: <具体到文件/目录/模块级别的资产清单>
- SKIP 什么: <这个项目里不要碰的部分及原因>
- 坑: <已知陷阱：版本重构、文档过时、云绑定、隐藏依赖…>
- recommendation: adopt | concepts-borrow
- 理由: <一句话>
- 与硬约束的冲突: <stdlib/离线/成本梯度/license 有无冲突及裁剪方式；无则写 无>

## 评估过但不推荐（skip 清单，防重爬）
- <id>（github.com/...）— skip：<一句话理由>
- ...

## 本 lane 的搜索方法沉淀
<用了哪些检索词/入口效果最好，哪些方向是死胡同——供未来 miner skill 起步>
```

字段语义对齐未来的 `reference/sources.yaml`（id/repository/license/mined_for/status），
汇合时可半机械转换。

## §6 执行方式（给主控 session 的编排指引）

1. **并行**：10 个 subagent 同时派发，每个只负责一个 lane，prompt 里贴入本文 §1–§3
   （公共背景与纪律）+ 该 lane 的 §4 定义 + §5 格式。
2. **只读**：调研工具限 WebSearch/WebFetch/读本仓库文件；不 clone、不安装、不执行
   被调研项目代码；不改 `src/`、`config/`、`data/`。
3. **时间盒**：单 lane 以"5–10 候选、2–3 推荐"为完成标准，宁可深挖推荐项也不要
   20 个浅条目。
4. **汇合**：全部 lane 完成后，主 session 写 `00-summary.md`：
   - 全局 Top 10 推荐表（跨 lane 排序：价值 × 可挖性 × 与硬约束的兼容度）；
   - 候选 `sources.yaml` 草稿（把 adopt/concepts-borrow 条目转成注册表格式）;
   - 全局 skip 清单合并；
   - 需要创始人拍板的事项（要引的依赖、license 灰区、live 抓取合规）。
5. **提交**：调研产物（L1–L10 + summary）提交回本仓库 master（创始人已授权直推）。
   提交信息建议：`docs(reference-scan): 10-lane 开源参考调研结果`。
