---
doc: research
lane: L9
title: "横切 A：LLM 基建"
date: 2026-07-07
agent: subagent
---

# L9 横切 A：LLM 基建

## 结论速览

推荐 **json-repair**（零依赖纯 Python 的 LLM JSON 修复器，MIT，可按"抄一个纯函数"路线直接落地，替换我们过于乐观的 `extract_json` 正则法）、**instructor**（业界事实标准的"schema 校验失败 → 把校验错误喂回 LLM 重问（reask）"闭环，模式可用 stdlib 复刻进 `RouterBackend.complete`）、**litellm**（多后端路由的 fallback 链/冷却/按错误类型重试策略/成本表，全部是可借的确定性模式，另附一份可直接搬的 `model_prices_and_context_window.json` 成本数据资产）。

**最重要的发现**：我们的 `runtime/llm.py` 缺的不是第五个后端，而是结构化输出的三层闭环——①对 `LLMRequest.schema` 做真校验（现在 schema 字段只用来决定"要不要 extract_json"，从不校验）；②校验失败时**带着错误信息重试**（现在的 retry 只重试网络异常，schema 不符的响应会以 `ok=True` 混进下游）；③重试前先过一层**容错修复解析**。三层都有成熟开源模式且都能纯 stdlib 落地，json_repair 本身就证明修复解析可以零依赖实现。另一发现：Anthropic/OpenAI 的 Batch API 均为 50% 折扣定价，我们 batch-first 的 `list[LLMRequest] -> list[LLMResponse]` 契约天然对齐——未来若接官方 batch 端点，只需新增一个后端而无需改任何 stage。

## 推荐候选（Top 2–3，按价值排序）

### json-repair
- repository: github.com/mangiucugna/json_repair
- stars: ~3k · license: MIT · 活跃度: 活跃（2026 年仍持续发版，被大量 agent 框架当依赖引用）；**单作者项目**（Stefano Baccianella），需标记，但代码体量小、被下游广泛背书，停更风险可通过"抄进来"消化
- mined_for:
  - 数据面: 无
  - 机制面: 容错 JSON 解析器——一个手写递归下降 parser，修复缺引号/缺逗号/缺括号/截断/夹杂散文的 LLM 输出；新版还支持 **schema 引导修复**（按 JSON Schema 填缺省值、安全类型强转如 "1"→1），与我们 `LLMRequest.schema` 字段直接同构
- 挖什么: `src/json_repair/` 整个包（核心是 `json_parser.py` 的递归下降解析 + `json_repair.py` 的 `loads/repair_json` 入口，配 `json_context.py` 解析状态机），纯 Python 零依赖，MIT。目标：提炼一个 ~200–400 行的 `runtime/jsonfix.py` 纯函数（`repair_loads(text) -> dict | None`），挂在 `extract_json` 的 json.loads 失败分支之后、正则兜底之前
- SKIP 什么: 其 CLI/streaming 包装与 Pydantic v2 集成入口（我们无 Pydantic）；性能优化的 `string_file_wrapper` 大文件流式路径（我们的响应都是短文本）
- 坑: 修复是"猜测意图"，可能把真正的坏输出静默修成合法但语义错的 JSON——修复后**必须**接 schema 校验（见 instructor 条目），且在 trace 里记 `repaired=true` 以便 retro 统计各后端的原始合格率
- recommendation: adopt
- 理由: 全 lane 唯一能按"抄一个纯函数"最高优先路线直接落地的候选：零依赖、MIT、体量小、解决的正是我们 `extract_json` 一旦正则失手就整条 response 报废的现实痛点
- 与硬约束的冲突: 无（纯 stdlib、离线、不涉及模型调用；抄代码需按仓库规矩走创始人点头 + 注明出处，MIT 允许）

### instructor
- repository: github.com/567-labs/instructor
- stars: ~13.4k · license: MIT · 活跃度: 非常活跃（2026-06-28 发 v1.15.4，110 个 release，100+ 贡献者，月下载 300 万+）
- mined_for:
  - 数据面: 无（其 prompt 片段与 Pydantic 强耦合，不可直接搬）
  - 机制面: ①**reask 闭环**：响应解析/校验失败时，把失败的 assistant 消息 + 一条 `"Please correct the function call; errors encountered:\n{errors}"` 用户消息追加进对话重发，`max_retries` 次内自愈——这是对我们最值钱的单个模式；②**Mode 分层**：同一契约下按 provider 能力选择 JSON mode / function-calling / MD_JSON（纯文本抽取）的枚举分派，对应我们 Router（LKEAP 无 response_format 保证）vs Dify vs CC 的差异化处理；③失败重试与"响应不合格"重试分离的异常分类（可与 litellm 的按错误类型重试互印）
- 挖什么: `instructor/core/retry.py`（reask 主循环：捕获校验异常 → 组装纠错消息 → 重发）、`instructor/core/exceptions.py`（异常分类）、`instructor/mode.py`（Mode 枚举与分派思想）、`docs/concepts/reask_validation.md` 与 `docs/concepts/retrying.md`（模式的权威描述，浓缩度比源码还高）。落地形态：给 `RouterBackend.complete` / `DifyBackend.complete` 增加"schema 校验失败 → 追加错误上下文重发一次"的分支；配一个 stdlib 的迷你 schema 校验器（我们 config/llm 里的 schema 只用到 type/properties/required/enum/数值范围这个子集，~100 行可覆盖）
- SKIP 什么: Pydantic 依赖面（整个 `from_provider` 客户端补丁体系、streaming partial、Iterable/parallel tools）；15+ provider 适配层——我们只有 OpenAI-compatible 一种线上形态
- 坑: 2025 年 v1.9–1.10 间做过大规模目录重构（旧文 `instructor/patch.py`/`retry.py` 已迁往 `instructor/core/`），挖矿时以 main 分支实际路径为准，网上教程大多指向旧布局；LLM-based validator（让另一个 LLM 判断输出）会引入额外调用，注意别把它带进便宜段
- recommendation: concepts-borrow
- 理由: 结构化输出强制的业界事实标准，其核心 reask 模式恰好补上我们"schema 从不校验、坏响应静默下行"的缺口，且模式本身与 Pydantic 可剥离、stdlib 可复刻
- 与硬约束的冲突: reask 意味着失败条目最多翻倍花钱——需按成本梯度裁剪：便宜段（generate/persona_sim）reask ≤1 次、失败即丢弃该条；昂贵段（judge）reask ≤2 次。绝不引 instructor 依赖本身（Pydantic 违反 stdlib 铁律）

### litellm
- repository: github.com/BerriAI/litellm
- stars: ~52.8k · license: MIT（注意仓库内 `enterprise/` 目录附商业条款，挖矿绕开该目录） · 活跃度: 极活跃（2026-07-04 发 v1.91.0，1300+ release，YC 公司维护）
- mined_for:
  - 数据面: `model_prices_and_context_window.json`（仓库根目录）——社区共同维护的全模型单价/上下文窗口表，可摘录我们在用的几个模型行落成 `config/llm/prices.json`，让 ledger/trace 从"记 token 数"升级为"记估算花费"，为成本梯度第一原则提供可观测数字
  - 机制面: ①**fallback 链与错误类型分派**：普通失败 / context window 超限 / 内容策略拦截各配不同的 fallback 目标（我们同构场景：Router 失败 → 降级 CC-handoff 包或 Mock，427 行以内可落）；②**按异常类型的 RetryPolicy**（`TimeoutErrorRetries: 3`、`RateLimitErrorRetries: 3`、认证错误不重试直接失败——我们现在对所有异常一视同仁地重试，浪费在必死的 401 上）；③**冷却（cooldown）**：连续失败的 deployment 移出可用池一段时间，429 立即冷却——对应我们 LKEAP 突发限流靠 `min_interval` 硬睡的原始做法
- 挖什么: `litellm/router.py`（fallback/retry 编排主体）、`litellm/router_utils/cooldown_handlers.py`（冷却判定）、`litellm/types/router.py` 里 RetryPolicy/AllowedFailsPolicy 的字段设计（比代码更值得抄的是这份**配置 schema 的词汇表**）、`model_prices_and_context_window.json`、docs 的 Fallbacks/Reliability 两页（模式浓缩）
- SKIP 什么: proxy/gateway 服务端（数据库+多租户，非目标）、100+ provider 适配层、企业目录 `enterprise/`、其 Python SDK 本体（重依赖，绝不引）
- 坑: 单文件 `router.py` 极大且演进快，抄逻辑前先读 docs 页确认当前语义再对照源码；`model_prices` json 是社区手工维护，个别条目滞后于官方调价，摘录时与官方价目页核对一遍；DeepWiki 上的结构图可能滞后于 40k+ commit 的真实布局
- recommendation: concepts-borrow
- 理由: 多后端路由可靠性工程的最全参考：错误分类重试 + 冷却 + fallback 链三个确定性模式直接补强 `backend_for_step`，外加一份唯一可直接 promote 的成本数据资产
- 与硬约束的冲突: 无 stdlib 冲突（借的都是控制流模式与 JSON 数据）；注意 fallback 链方向必须"贵→便宜/离线"（Router→CC/Mock），不许配置成"便宜段失败自动升级贵模型"，否则违反成本梯度

## 评估过但不推荐（skip 清单，防重爬）

- outlines（github.com/dottxt-ai/outlines）— skip：核心价值是 logits 级约束解码，只对本地推理（可挂 LogitsProcessor）成立；对我们这种纯远程 OpenAI-compatible 后端只剩 response_format 透传的薄封装，无可挖机制。
- baml（github.com/BoundaryML/baml）— skip：Schema-Aligned Parsing（SAP，"以 schema 为导向解析任意脏输出，免重试"）思想极好，但实现是 Rust jsonish parser + 自研 DSL/codegen 全家桶，Python 侧借不到代码；SAP 的实用效果已由 json_repair（schema 引导修复）+ instructor（reask 兜底）组合覆盖。其博客 boundaryml.com/blog/schema-aligned-parsing 值得一读，仅此而已。
- prompty（github.com/microsoft/prompty）— skip：YAML frontmatter + markdown 正文的 prompt 资产格式规范不错（~1.1k stars，微软维护），但我们已有 config/llm/*.json ↔ dify/flows/*.yml 双真相 + CI 镜像钉，再引第三种格式只会增加同步负担；可借的仅是 frontmatter 元数据字段命名（model/inputs/sample）作 config/llm 字段演进参考。
- langfuse（github.com/langfuse/langfuse）— skip（本 lane 视角）：prompt 版本管理的数据模型值得借一句话——**version 是不可变自增历史，label（prod/prod-a/prod-b）是可移动指针，A/B = 两个 label 随机取用 + 按 label 聚合指标**；这可以纯文件落地（config/llm/versions/ + trace 里已有的 prompt_version 加一个 label 字段），不需要它的数据库平台。整体项目归 L10（可观测）评估。
- routellm（github.com/lm-sys/RouteLLM）— skip：按 query 难度在强/弱模型间分流省 75–85% 成本的研究框架，思想与我们成本梯度同源，但需要训练好的 router 模型 + 重依赖，且我们的分流单位是"漏斗阶段"而非"单条 query"，`backend_for_step` + per-step `model_env` 已是它的确定性等价物。
- guardrails（github.com/guardrails-ai/guardrails）— skip：validator 走云端 Hub 分发、依赖重，校验器生态对我们过剩；reask 思想与 instructor 重复且实现更绕。
- gateway（github.com/Portkey-AI/gateway）— skip：TS/JS 实现的 AI 网关，config 驱动的 fallback/loadbalance schema 设计尚可，但模式与 litellm 完全重叠，无需重复登记。
- llm（github.com/simonw/llm）— skip：优秀的交互式 CLI + SQLite 日志工具，但形态是"人对话一条"而非"管线批处理"，模板/schema 机制与我们 batch-first 契约不合。
- promptlayer — skip：核心是 SaaS，开源部分薄，无可挖资产。

## 本 lane 的搜索方法沉淀

- 最有效入口：**目标项目的 docs/concepts/ 目录**（instructor 的 reask_validation.md、litellm 的 reliability 文档页）——模式浓缩度远高于源码本身，先读 docs 定位模式、再按需下钻源码文件，是"只挖不跑"的最省 token 路径。
- 检索词模板：`<repo> retry reask validation`、`<repo> fallback cooldown retry policy` 这类"项目名 + 机制词"组合比泛搜"LLM structured output best practices"精准得多；DeepWiki（deepwiki.com/<org>/<repo>）对大仓库的结构导航有用，但注意可能滞后。
- 验证现状必做：直接 fetch GitHub 仓库首页拿 stars/最新 release 日期/license，搜索引擎摘要里的数字普遍过时 6–18 个月（instructor 一处写 11k 实为 13.4k）。
- 死胡同：①"constrained decoding / grammar-based sampling"方向（outlines/sglang/vllm 系）整个分支对远程 API 后端不适用,今后此 lane 不必再爬；②"prompt engineering 模板库"检索会捞回大量无方法论的 prompt 堆,与 LLM 基建无关；③batch API 成本优化没有独立的可登记开源项目,它是各家官方 API 的定价属性（Anthropic Message Batches / OpenAI Batch 均 50% off,24h 窗口）,结论直接写进设计即可。
