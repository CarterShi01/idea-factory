# LLM Agent 编排框架选型调研：为 idea-factory / idea-evl 每日多源 idea 管线选栈

## 调研背景与目标场景

你要构建的核心管线是一个**每日定时、多源、链式**的流水线：

> 外部事件采集（HN / Product Hunt / RSS）+ 用户脑海 idea 录入 + 模拟目标人群痛点分析 → 归一化 → 生成结构化 idea 候选 → 评估打分（idea-evl）→ 去重 → 排序 → 每天稳定输出 10~20 条「靠谱」idea。

这个场景的本质不是「实时对话型 agent」，而是一个 **batch / DAG 风格的离线作业**，对编排框架的要求排序是：

1. **可靠的链式 / DAG 编排**（多阶段、可分支、可并行采源）
2. **可观测性**（每天跑，必须能回溯某条 idea 是怎么生成、为何被淘汰的）
3. **一人公司友好**：低运维、本地可跑、不需要起一堆服务
4. **与现有 `src/idea_factory/` Python src 布局契合**（当前 pipeline.py/normalize.py/generate.py/ranks.py/export.py 已经是「阶段函数」结构）
5. **成本可控**（token 成本 + 框架本身不绑定昂贵云）

下面对题面列出的框架逐一对照，再给推荐栈。

## 框架全景对照表

| 框架 | 类型 | 语言 | 编排模型 | 学习曲线 | 可观测性 | 本地/自托管 | 2026 状态 | 适合一人公司？ |
|---|---|---|---|---|---|---|---|---|
| **LangGraph** | 代码库 | Python/TS | 有状态图（node/edge + checkpoint） | 陡（需图设计） | LangGraph Studio + LangSmith（SaaS，自托管要企业版） | ✅ 库，MIT，零部署门槛 | 生产级，月下载 47M+，3 月加 OTel | 强，但偏重 |
| **LlamaIndex Workflows** | 代码库 | Python | 事件驱动 `@step`（typed Events + Context） | 中 | OTel / 第三方 | ✅ 库 | 活跃，配 llama-deploy + Eval | **很适合**（结构最贴近本管线） |
| **CrewAI** | 代码库 | Python | 角色化 agent team + task | 最平缓 | Enterprise AMP 可视化 | ✅ 库 | v1.14，A2A 协议 | 适合快速原型 |
| **AutoGen / AG2** | 代码库 | Python | 多方对话 / group chat | 中 | MemoryStream 事件回放 | ✅ 库 | ⚠️ 微软原 AutoGen 已进维护模式，并入 Microsoft Agent Framework（v1.0 GA, 2026-04）；社区由 **AG2** 接棒 | 不推荐（对话型，非本场景） |
| **OpenAI Agents SDK**（原 Swarm） | 代码库 | Python（TS 计划中） | handoff + sessions | 最简单 API | **内置 tracing**（dashboard，可导出 Logfire/Braintrust） | ✅ `pip install openai-agents` | 生产级，2026-04 harness 升级 | 适合，但偏 OpenAI 生态 |
| **Dify** | 平台/可视化 | —（API） | 可视化 LLM app canvas + RAG | 低（无代码） | 平台内置 | ⚠️ 自托管需 7+ 服务（API/worker/web/PG/Redis/向量库/sandbox） | 活跃 | 偏重，运维成本高 |
| **n8n** | 平台/低代码 | —（JS 节点） | 节点画布 + 500+ 集成 + **原生定时** | 低 | 平台内置执行记录 | ✅ 单容器 Docker，自托管最省心 | 活跃 | 适合「胶水/调度层」 |
| **Mastra** | 代码库 | **TypeScript** | 图工作流 `.then()/.branch()/.parallel()` + 暂停恢复 | 中 | ops 友好 observability | ✅ 库，MIT | v1.0（2026-01），22k★，A 轮 $22M | 适合 TS 团队，但你是 Python |
| **PocketFlow** | 极简库 | Python（多语言移植） | Graph + Shared Store，**核心仅 100 行**，零依赖 | 极低 | 自己接（无内置） | ✅ `pip install pocketflow` 或直接拷源码 | 活跃，社区小 | 极适合做内核，但要自己补料 |

> 关键事实核实（WebFetch 确认）：
> - **AutoGen 已进维护模式**，微软将 AutoGen + Semantic Kernel 合并为 **Microsoft Agent Framework（2026-04 v1.0 GA）**；新项目不应再选原 AutoGen，社区延续走 **AG2**。
> - **LangSmith 闭源**，自托管是企业版付费 add-on；要免费自托管可观测性应选 **Langfuse（MIT，ClickHouse 自托管）** 或 **Arize Phoenix（OTel 原生）**。
> - **OpenAI Agents SDK** 是「自带 guardrails/sessions/handoffs/tracing 的最小框架」，`pip install openai-agents`，Python 3.9+，原生 MCP。

## 按你的具体场景做取舍

### 不推荐的（针对本场景）

- **AutoGen / AG2**：强项是「多 agent 多轮辩论 / group chat」，你的管线是确定性的 DAG，不需要 agent 互相吵架。维护模式更是减分。
- **Dify**：AI 是「产品本身」（chatbot/RAG 工具）时才划算；你的 AI 只是流水线中的若干步。自托管 7+ 服务对一人公司是负担，违反你 CLAUDE.md「demo 不引入数据库/复杂多 agent 框架」的非目标。
- **Mastra**：很优秀，但 TypeScript。你已有 `src/idea_factory/` Python 布局，跨语言迁移成本不值得。
- **CrewAI**：角色化 team 适合「市场调研自动化」这类松散协作，但它对「严格的每日 DAG + 去重 + 排序」帮助有限，容易把简单流水线包装成过度抽象的 agent crew。

### 候选三强

1. **LangGraph** — 最 battle-tested 的有状态编排。优点：checkpoint / 持久化 / human-in-the-loop（你后面想加「人工挑 idea」时直接用上）、LangGraph Studio 可视化回放单条 idea 的全过程。缺点：图 API 较重、boilerplate 多、最佳可观测性 LangSmith 要付费/SaaS。
2. **LlamaIndex Workflows** — **结构最贴合**。`@step` 函数消费/发射 typed Event，runtime 按类型路由——这几乎就是你「采集事件→归一化→生成→评估→去重→排序」逐级 emit 的天然写法，比 LangGraph 的图状态机更轻、更 Pythonic，且自带 Eval 子系统（对 idea-evl 直接有用）。
3. **PocketFlow** — 100 行内核、零依赖、零供应商锁定。适合「先不上重框架」：把你现有 pipeline.py 的阶段直接映射成 Node + Action，**几乎零迁移成本**，且不违反「保持离线/轻量」的项目铁律。代价是可观测性、重试、checkpoint 都要自己补。

### 调度层（与编排框架正交，别混为一谈）

每日定时本身**不需要**让编排框架来扛。两条路线：

- **极简**：`cron` + 一个 Python 入口（你已有 `idea-factory` console entrypoint）。低开销、可靠，对「每天一次的确定性作业」完全够用，符合 demo 非目标（不上数据库/部署自动化）。
- **进阶**：当需要重试、依赖管理、失败告警时，再引入 **Prefect**（Cron/Interval/RRule 三种 schedule、轻量、Python 原生），它与 LangGraph/LlamaIndex 都能并存。**不建议**一上来就 Airflow（对一人公司过重）。

## 推荐栈（分阶段）

**阶段一（现在，0 改动哲学）— 保持离线 demo 契约**
- 编排：**PocketFlow** 或干脆**保留现有手写 pipeline.py**（你的阶段函数已经是事实上的 DAG）。
- 调度：**cron** 调用 `idea-factory`。
- 可观测性：先用结构化日志 + 把每阶段中间产物落到 `data/processed/`（已有），方便回溯。
- 理由：满足 CLAUDE.md「最小改动、离线、不引入复杂多 agent 框架」。

**阶段二（接入真实多源 + LLM 生成/评估时）— 推荐主力栈**
- 编排：**LlamaIndex Workflows**（首选，事件驱动最贴合）或 **LangGraph**（若你重视 Studio 可视化 + checkpoint）。
- LLM 调用层：因你是 Anthropic/Claude 生态，可用 **Claude Agent SDK** 或直接 SDK 调模型；若选 OpenAI 生态则 **OpenAI Agents SDK**（自带 tracing，最省事）。
- 调度：**Prefect**（cron schedule + 重试 + 失败告警）。
- 可观测性：**Langfuse（自托管，MIT，免费）** 或 **Arize Phoenix（OTel 原生）**——避开 LangSmith 的企业自托管付费墙。
- 成本：框架本身全部免费/开源；主要成本是 LLM token。每天 10~20 条 idea 的量级，用 batch 调用 + 对去重/初筛用小模型、对终评用大模型，可显著压成本。

## 对 idea-factory / idea-evl 的具体借鉴与可落地建议

1. **idea-factory：不要急着上重框架，先把现有 pipeline 显式化为「事件/阶段」契约。** 你的 normalize→generate→rank→export 已是阶段化，建议先把阶段间数据定义成**带 schema 的 typed 记录**（dataclass/pydantic）。这一步无论将来选 LlamaIndex Workflows（typed Event 直接对应）还是 LangGraph（state 对应）都能平滑迁移，且本身不引入任何网络/依赖，符合离线契约。

2. **三个源头建议建模为三个独立「采集 step」并行 fan-in。** 外部事件（复用现有 `collect.py` 的 HN/PH/RSS）、用户 idea 录入（一个本地文件/CLI 输入 step）、模拟痛点分析（一个 LLM step）——三路并行产出统一的「signal 记录」，再汇入归一化。LlamaIndex Workflows 的 event 路由或 LangGraph 的并行 node 都原生支持这种 fan-out/fan-in，避免你手写并发。

3. **去重要做成显式独立 step，并用「payload 哈希 + job ID」幂等。** 调研显示成熟管线靠 payload hashing 跳过重复（dedup < 50ms）。你已有 `match.py` 做关键词匹配，可升级为：先哈希/规则粗去重（便宜），再对疑似重复用 LLM 语义判重（贵但准）。这条直接复用现有 match.py 投入。

4. **idea-evl 用「Eval 子系统」思路而非「再造一个 agent 框架」。** 评估打分本质是 LLM-as-judge + 规则打分的组合。**LlamaIndex 自带 Eval**、LangSmith/Langfuse 都有 evaluation 原语。建议 idea-evl 定义为：输入一批 idea 候选 → 多维度打分（市场信号强度、与现有 idea 重复度、可执行性）→ 输出分数 + 理由。把它做成一个**可被 idea-factory 的 rank step 调用的库**，而不是独立服务（符合「无 DB、无多服务」非目标）。

5. **可观测性现在就埋点，别等出问题。** 每天产 10~20 条且要「靠谱」，你必然需要回答「为什么今天这条进了 top、那条被淘汰」。建议第二阶段接 **Langfuse 自托管**（单容器、MIT、免费），对每条 idea 的生成 prompt、评估理由、淘汰原因全链路 trace。这是闭源 LangSmith 之外对一人公司最现实的选择。

6. **调度与编排解耦，先 cron 后 Prefect。** 别让 LangGraph/LlamaIndex 去管「每天几点跑」。用 cron 触发 `idea-factory` 入口；当你开始需要「失败重试、跑了一半挂掉续跑」时再引入 Prefect 或 LangGraph 的 checkpoint。这样能保持现阶段 demo 的极简与离线契约。

## 一句话结论

**一人公司、Python src 布局、每日 batch 管线**的最优解不是「最火的多 agent 框架」，而是：**现阶段用 PocketFlow / 手写 pipeline + cron 保持离线轻量；接真实数据后主力切到 LlamaIndex Workflows（或 LangGraph）+ Prefect 调度 + Langfuse 自托管可观测**。避开 AutoGen（维护模式）、Dify（自托管太重）、Mastra（语言不符）。

## 参考链接

- 2026 框架对照（含 AutoGen 维护模式 / MS Agent Framework GA）：https://qubittool.com/blog/ai-agent-framework-comparison-2026
- LangGraph vs CrewAI vs AutoGen vs Custom 基准：https://tensoria.fr/en/blog/multi-agent-orchestration-comparison
- 开源 agent 框架对比（OpenAgents）：https://openagents.org/blog/posts/2026-02-23-open-source-ai-agent-frameworks-compared
- LlamaIndex Workflows vs LangGraph（事件驱动 vs 状态机）：https://medium.com/@pedroazevedo6/langgraph-vs-llamaindex-workflows-for-building-agents-the-final-no-bs-guide-2025-11445ef6fadc
- LlamaIndex 2026 指南（Workflows + Eval + llama-deploy）：https://futureagi.com/blog/exploring-llamaindex-a-powerful-tool-for-llms/
- n8n vs Dify 自托管对比（Jimmy Song 开源平台对比）：https://jimmysong.io/blog/open-source-ai-agent-workflow-comparison/
- n8n vs Dify 详细对比（含自托管服务数/价格）：https://hostadvice.com/blog/ai/automation/n8n-vs-dify/
- PocketFlow 官方（100 行 LLM 框架）：https://github.com/The-Pocket/PocketFlow
- PocketFlow 文档：https://the-pocket.github.io/PocketFlow/
- Mastra 官网（TypeScript agent 框架）：https://mastra.ai/
- Mastra 完整指南 2026：https://www.generative.inc/mastra-ai-the-complete-guide-to-the-typescript-agent-framework-2026
- OpenAI Agents SDK（GitHub，lightweight 多 agent）：https://github.com/openai/openai-agents-python
- OpenAI Agents SDK 文档（MCP / tracing）：https://openai.github.io/openai-agents-python/
- LangSmith 自托管限制与 Langfuse/Phoenix 替代（Laminar）：https://laminar.sh/blog/2026-01-29-laminar-vs-langfuse-vs-langsmith-llm-observability-compared
- Langfuse 等开源可观测性（MLflow top 5）：https://mlflow.org/top-5-agent-observability-tools/
- Prefect 调度（Cron/Interval/RRule）：https://docs.prefect.io/v3/concepts/schedules
- 编排工具选型（Prefect 官方博客）：https://www.prefect.io/blog/orchestration-tools-choose-the-right-tool-for-the-job
- cron 调度数据管线（DataCamp）：https://www.datacamp.com/tutorial/cron-job-in-data-engineering
- LLM 编排框架/RAG 对比（ZenML）：https://www.zenml.io/blog/best-llm-orchestration-frameworks
