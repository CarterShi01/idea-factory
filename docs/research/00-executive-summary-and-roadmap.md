# 执行摘要与落地路线图

> 本报告综合 9 份分层调研（idea 生成项目、agent 编排框架、量化范式、外部信号源、痛点挖掘、idea 评估方法论、自动化假设生成、商业 SaaS 竞品、系统架构/记忆、一人公司工作流），面向你本人，给出一份"读一页就能决策、照着做就能落地"的执行摘要 + 分阶段路线图。

---

## 一、一页执行摘要（最关键的 7 条结论）

1. **你的直觉是对的，且已被学术与工程双重验证："每天产出并筛选 idea"在结构上等价于一条量化研究流水线**——信号(signal)→因子(factor)→打分(alpha)→回测(backtest)→组合(Top-N)→风控。idea-factory 负责"因子化生成与打分"，idea-evl 负责"回测式事后验证与裁决"。这条主线贯穿全报告。

2. **三源融合是你真正的差异化护城河。** 全网竞品（Exploding Topics、IdeaBrowser、GummySearch、PainHunt…）**没有一家把【外部事件】+【脑海 idea】+【模拟人群痛点】三源合一**——趋势工具不生成 idea，idea 工具不接真实信号，痛点工具刚因平台政策死掉。把三源拼成一条每日稳定流水线，正是市场缺口。

3. **"生成 idea"已被 LLM 平民化、不值钱了；"验证需求/高效淘汰"才是稀缺价值。** 2026 年共识：好点子遍地，已验证需求极少，纯 AI 生成的 idea 普遍"千篇一律、TAM 数字编造"。因此 **idea-evl 是系统的价值重心**，它的第一职责不是"找出神 idea"，而是像投资人 screening 一样"高效说不"。

4. **数据源单点风险是头号杀手，必须工程化对冲。** GummySearch（14 万用户）于 2025-11-30 因拿不到 Reddit 商业 API 授权而关停——教科书级"平台风险"案例。结论：**Reddit/Crunchbase 不进 demo 主路径**；基本盘用零成本合规源（HN Firebase+Algolia、arXiv、GitHub Trending RSS、各类 newsletter RSS），信号源做成可插拔可降级。

5. **生成阶段的高分会"虚高"，必须有执行视角的二次评估闸门。** Stanford 实验：LLM idea 新颖度显著高于人类、但可行性更弱；后续"Ideation-Execution Gap"研究显示真正执行后 LLM idea 各项指标下降幅度远超人类、排名甚至反转。这恰恰是 idea-evl 存在的根本理由——不能让 ideation 的高分直接当结论。

6. **多样性 ≠ 调高 temperature。** 稳定每日产出而不重复的最大敌人是 mode collapse（根因是对齐训练的 typicality bias）。最低成本、最高收益的解法是 **Verbalized Sampling**（让模型一次给出 N 条候选+各自概率，已核实可带来 1.6–2.1× 多样性提升），配合 embedding 去重存活率（Non-Duplicate Ratio）作为每日质量指标。

7. **保持"反非目标"纪律。** 不引入 Web UI、不引入数据库服务、不引入复杂多 agent 框架——除非路线图明确推进到对应阶段。现有 `collect.py` 的适配器模式 + `_blank_record()` 统一 schema + `_stable_id()` + `run_scheduled()` 已经是很好的地基，演进而非重写。

---

## 二、是否存在可直接 fork 的项目？结论性回答

**结论：没有任何一个仓库适合"整体 fork 当底座"；但有一个仓库必须逐文件拆解借鉴。**

- **`MaxKmet/idea-validation-agents`（MIT，266 star / 27 fork，已 WebFetch 核实）** 是目标对齐度最高的对象。它做了"多源采集→生成 7-10 条带评分 idea→九步验证→裁决"，产物落地为 `ideas/<name>/scores.json`、`competitors.json`、`pricing.json`、`decision_memo.md`，并把"最危险假设 + ≤2 周/≤$100 实验"写进决策备忘。**但它是 prompt-config 驱动**（靠 `CLAUDE.md`/`AGENTS.md`/Cursor rules，无 Python 流水线、无离线 demo、信号靠 agent 实时抓取），与你的 `src/` 布局和离线契约不兼容。
- **正确策略：fork 不必，逐文件搬运必须。** 把它的三样东西搬进你现有代码：①**多重-下限（multiplicative-floor）评分算法**（一个致命短板直接归零）→ idea-evl 的打分核心；②**九步验证清单 + 决策备忘模板**（`decision_memo.md` 含"最危险假设"和"≤2周/≤$100 实验"）→ idea-evl 的输出形态；③**Van Westendorp 定价 / 1星3星评论挖掘 / 预 mortem** 等具体子例程。
- 其余开源只是"半成品零件"：`reddit-saas-idea-finder`（信号词典，与你 collect.py+match.py 同构）、`RedditMiner`（批量生成+Markdown 导出）、`llm-scraper`/Firecrawl（网页→结构化）、LangGraph/CrewAI（编排）。学术侧 `AlphaAgent`（KDD'25，已核实）提供了"Idea Agent→Factor Agent→Eval Agent"的完整闭环范式，是 idea-factory↔idea-evl 双仓协作的理论模板。

---

## 三、推荐的整体系统蓝图与职责边界

```
  [外部事件变化]        [脑海 idea 录入]        [模拟人群痛点分析]
  collect.py            inbox.jsonl            persona prompts
  HN/Algolia/arXiv/     (你随手记)             (绑定真实 verbatim,
  GH Trending/RSS                               打 confidence=synthetic)
        \                    |                       /
         \                   |                      /
          v                  v                     v
   ┌───────────────────────────────────────────────────┐
   │  归一化 → 统一信号 schema (含 timestamp + dedup_key) │  ← idea-factory: normalize.py
   └───────────────────────────────────────────────────┘
                            │
              精确去重(id/hash) → 语义去重("已见过", embedding KNN<τ)
                            │ (仅"新"信号通过)
                            v
   ┌───────────────────────────────────────────────────┐
   │  生成 idea 候选：发散(过量40-60条, Verbalized Sample)│  ← idea-factory: generate.py
   │  → 去重 → 因子化打分(market_freshness/pain_intensity│     + 新 dedup stage + 因子库
   │  /build_cost/moat/competition/distribution_fit…)    │
   └───────────────────────────────────────────────────┘
                            │  携带每个因子分 + freshness/decay
                            v
   ┌───────────────────────────────────────────────────┐
   │  前期评估/裁决：多维 rubric + LLM-as-judge +        │  ← idea-evl
   │  对抗式批判(devil's advocate) + 多重-下限(kill gate)│     score/rationale/decision_memo
   │  + 反谄媚 + 事后命中率回测                          │
   └───────────────────────────────────────────────────┘
                            │  按分阈值路由
              ┌─────────────┴──────────────┐
              v (高分: auto-keep)          v (中分/不确定: 人审队列)
        进入排序 Top-N                 review_queue.jsonl
              └─────────────┬──────────────┘  approve/reject/edit
                            v
            排序去重出 10-20 条 + Markdown 报告(export.py)
                            v
            feedback.jsonl 回流(调阈值/调prompt/做eval校准)
```

**职责边界（务必清晰，避免两仓逻辑漂移）：**

| 维度 | idea-factory | idea-evl |
|---|---|---|
| 类比量化 | 信号采集 + 因子计算 + alpha 打分 | 回测 + 风控 + 组合裁决 |
| 输入 | 三源原始信号 | idea-factory 产出的候选+因子分 |
| 核心产物 | 结构化 idea 候选（带因子分、freshness、stable id） | score(0-100) / decision_memo / kill 判定 / 命中率统计 |
| 关键原则 | 量大、去噪、不在生成阶段过度纠结 | 高效淘汰、对抗式批判、防 ideation 虚高 |
| 共享 | **因子定义必须共用同一套**（freqtrade 铁律：评估逻辑与生产逻辑共用因子，否则回测出的"靠谱"在生产时失真） | 同左 |

---

## 四、量化范式 → 本项目的核心映射表

| 量化范式 | 本项目映射 | 落到哪个仓 | 可落地动作 |
|---|---|---|---|
| Signal（高时效低信噪比事件流） | 三源信号，**带时间戳逐条进入** | idea-factory | collect.py 已就位；强制每条带 `launched_at`/`collected_at` |
| Factor（标准化可比特征） | **idea 因子库**：`market_freshness`/`pain_intensity`/`build_cost`/`moat_signal`/`competition_density`/`distribution_fit` | idea-factory | 每个因子 = 纯函数 `record→float`，可单测、可版本化 |
| Alpha（排序分） | 因子加权得到 idea 候选排序分 | idea-factory→evl | 5 维左右加权（对齐 IdeaProof/IdeaBrowser 共性） |
| Signal decay（半衰期） | **idea 机会窗口会衰减**：刚发生含金量最高，越多人看越拥挤 | idea-factory | `score *= exp(-λ·age)`；对"人人能想到"的机械型 idea 主动降权 |
| Backtest（用历史证伪） | **事后命中率**：把过去 3-6 月产出的 idea 拉出来，对照后来是否真出现类似产品/痛点被验证 | idea-evl | 统计 hit ratio，校准 rubric |
| Lookahead bias | point-in-time 评估：只用"当天已存在"的信息 | idea-evl | watermark + incremental，禁用未来信息 |
| Originality 正则（AST 同构惩罚） | **惩罚与历史已产出 idea 雷同的新 idea**（去重/反拥挤） | idea-evl | embedding 距离 < τ 则降权/淘汰 |
| Hypothesis alignment | 检查 idea "痛点—方案—目标人群"三者逻辑自洽，过滤幻觉 | idea-evl | CoT 先推理后打分 |
| Complexity control（防过拟合） | 偏好一人公司可落地的简单 idea，惩罚"需 50 人团队"的宏大叙事 | idea-evl | build_cost 因子 + kill gate |
| Portfolio Top-N + 风控 | 每日排序出 10-20 条，控制方向拥挤（diversity） | idea-factory | 同时优化 novelty（单条够新）与 diversity（整组够广） |

---

## 五、分阶段路线图（每阶段：产出 + 依赖 + 验收）

> 原则：每阶段都是一个可独立交付、不破坏离线 demo 契约的小步。先用规则/embedding 搭骨架，LLM 后接。

### 阶段 0 — 现有离线 demo 能立刻做的（0 新依赖）
- **产出**：把 `MaxKmet` 的多重-下限评分算法 + 23 点验证清单（IdeaKiller 口径，已多处一致）落成 idea-evl v1 rubric，先用规则版打分跑通 sample_products.json。新增 `dedup` stage（generate 与 rank 之间，embedding/简单去重）。
- **依赖**：stdlib + 现有 src 结构。
- **验收**：`idea-factory` 端到端跑通，输出带 score 与 kill 标记的 Markdown；同一输入两次运行结果稳定（stable id 去重生效）。

### 阶段 1 — 接外部源（opt-in，不进默认 demo 路径）
- **产出**：扩 collect.py 加 HN Algolia（`search_by_date`+时间窗计数）、arXiv、GitHub Trending RSS；实现"滑动窗口计数 + Moving Z-Score"突增检测（纯 stdlib），给话题打 `rising/steady/peaked` + `growth_speed`。
- **依赖**：仅网络（已有可注入 get_json/get_text 适配器）；**不引入 Reddit/Crunchbase**。
- **验收**：`collect` 跑出带 freshness 标签的真实信号；离线 `idea-factory`（不联网）仍照常工作。

### 阶段 2 — 加评估闸门（idea-evl 成形）
- **产出**：idea-evl 实现多维 rubric + LLM-as-judge + 对抗式批判(devil's advocate) + 反谄媚（生成与评估用不同 prompt/模型，避免 self-enhancement 偏差）；输出 `decision_memo.md`（含最危险假设 + ≤2周/≤$100 实验建议）。
- **依赖**：1 个 LLM API（首选 Anthropic tool-use 做强约束 JSON 抽取，失败率可降到 0.1% 以下）。
- **验收**：拿 10-30 条人工打过分的 idea 做基准，LLM 与人工一致性达标（Krippendorff's α ≈ 0.8）。

### 阶段 3 — 加记忆/去重/状态机
- **产出**：持久化"已见过"状态（精确 hash + 语义 KNN 去重）；idea 候选带状态字段 `new/screened/diligence/pursue/parked/killed`（CRM 式 deal-flow 跟踪）；run trace 写 `runs.jsonl` 做成本/可观测。
- **依赖**：可上 **sqlite + sqlite-vec**（单文件，不算"数据库服务"，不违反非目标）；否则 jsonl + embedding 文件兜底。
- **验收**：连续多日运行，重复 idea 被正确拦截；可回溯任一条 idea "怎么生成、为何被淘汰"。

### 阶段 4 — 稳定每日 10-20 条 + 人审闭环
- **产出**：发散(40-60条 Verbalized Sampling)→去重→收敛(Top 10-20)；第 3 源头（持续接入），痛点信号绑定真实 verbatim + `confidence=synthetic` 标签且需"≥1 条真实信号佐证"才升级；30-60 分钟/天人审队列 + feedback 回流。
- **依赖**：定时调度——**主用 GitHub Actions schedule**（已核实：60 天无 commit 会被静默禁用且连带禁用非定时触发器），**必须加 keepalive（如 efrecon/gh-action-keepalive）+ 心跳告警（healthchecks.io）**；本地/VPS 用现有 `run_scheduled()` 作兜底。
- **验收**：连续 2 周每天稳定产出 10-20 条、Non-Duplicate Ratio 达标、人审通过率与命中率开始可统计。

---

## 六、推荐技术栈 + "反非目标"提醒

**推荐栈（一人公司友好、与 Python `src/` 布局契合）：**
- **编排**：当前阶段**不上重框架**。优先 **PocketFlow**（100 行内核、零依赖，可把现有 pipeline.py 阶段直接映射 Node+Action，几乎零迁移）；若需 typed event 路由与内建 Eval，再考虑 **LlamaIndex Workflows**（结构最贴合"逐级 emit"）。LangGraph 留作"将来要 human-in-the-loop checkpoint 回放"时再评估。
- **不选**：AutoGen（已进维护模式，且对话型非本场景）、Dify（自托管 7+ 服务）、Mastra（TypeScript）、CrewAI（角色化 team 对确定性 DAG 帮助有限）。
- **可观测性**（如要免费自托管）：Langfuse 或 Arize Phoenix（OTel 原生），不必绑 LangSmith（闭源/SaaS）。
- **存储**：jsonl 起步 → 需要语义去重时 sqlite + sqlite-vec（单文件）。
- **LLM 抽取**：Anthropic tool-use 做强约束 JSON。

**反非目标提醒（来自 CLAUDE.md / project-brief）：**
- 不加 Web UI、不加数据库服务、不加复杂多 agent 框架——除非路线图到了阶段 3/4 且确有必要。
- 网络只在显式 `collect` 发生，离线 demo 主路径永远不联网。
- 信号源默认 opt-in 且不商用（Product Hunt 默认条款禁商用；Reddit 需预审批）。

---

## 七、风险与开放问题

| 风险/问题 | 说明 | 缓解 |
|---|---|---|
| **数据源平台风险** | GummySearch 之死证明重度依赖单一平台 API 政策一变即归零 | 信号源可插拔可降级；基本盘只用零成本合规源 |
| **合成痛点假阳性** | persona 系统性偏乐观、谄媚，几乎对任何点子点头 | devil's advocate + trait 注入 + 绑定真实 verbatim + `confidence=synthetic` |
| **ideation 虚高** | 生成阶段高分执行后大幅缩水 | idea-evl 做执行视角二次评估 + 事后命中率回测 |
| **mode collapse** | 每日产出趋同 | Verbalized Sampling + embedding 去重 + 同时优化 novelty/diversity |
| **LLM-as-judge 偏差** | verbosity/position/self-enhancement/overconfidence | 长度归一化、随机顺序、生成≠评估用不同模型、要求输出置信度 |
| **调度静默失败** | GitHub cron 漂移 + 60 天禁用 | keepalive + 心跳告警 + 本地兜底 |
| **两仓因子漂移** | 评估逻辑与生产逻辑不一致 → 回测失真 | 因子定义单一来源、两仓共用 |
| **开放问题** | (1) 第 3 源头痛点模拟的最小可信版本如何定义？(2) 命中率回测需要多久样本才有统计意义（建议先攒 3-6 月）？(3) idea 因子的初始权重如何标定——建议用 10-30 条人工标注先校准再迭代。 | — |

---

## 参考链接

- MaxKmet/idea-validation-agents（MIT，266★，已核实 pipeline 与产物）: https://github.com/MaxKmet/idea-validation-agents
- AlphaAgent: LLM-Driven Alpha Mining with Regularized Exploration to Counteract Alpha Decay (KDD'25): https://arxiv.org/abs/2502.16789
- QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining: https://arxiv.org/html/2602.07085
- Verbalized Sampling: How to Mitigate Mode Collapse and Unlock LLM Diversity: https://arxiv.org/abs/2510.01171
- Verbalized Sampling 代码库: https://github.com/CHATS-lab/verbalized-sampling
- GummySearch 关停官方说明: https://gummysearch.com/closing-time/
- GummySearch 关停分析（平台风险）: https://syncsuptech.substack.com/p/gummysearch-shuts-down
- GitHub Actions 60 天禁用官方文档: https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow
- efrecon/gh-action-keepalive（防 60 天禁用）: https://github.com/efrecon/gh-action-keepalive
- "Idle scheduled workflow disabling also disables non-scheduled triggers" 讨论: https://github.com/orgs/community/discussions/32197
- idea-validation GitHub Topic（同类零件参考）: https://github.com/topics/idea-validation
