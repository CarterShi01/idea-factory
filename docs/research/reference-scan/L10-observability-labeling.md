---
doc: research
lane: L10
title: "横切 B:可观测、trace 与操作即标签"
date: 2026-07-07
agent: subagent
---

# L10 横切 B:可观测、trace 与操作即标签

## 结论速览

推荐 **langfuse**(MIT,score/ScoreConfig/annotation-queue 数据模型几乎逐字段映射我们的 verdicts.jsonl 与"操作即标签")、**openinference**(Apache-2.0,trace 属性命名规范 + 10 种 span kind,扁平 dot-namespace 天然适配 jsonl)、**label-studio**(Apache-2.0,标注事件元数据字段 lead_time/was_cancelled/ground_truth 是我们 do_label 缺失的)。

**最重要的发现**:LLM 可观测生态无一例外重数据库(langfuse/opik/phoenix/laminar 全部 ClickHouse 系)——"读文件、无数据库的 web 漏斗仪表盘"**没有可整仓借鉴的开源先例**,最接近的只有终端工具(lnav/klp)和 sqlite 工具(datasette)。所以本 lane 的正确挖法是:挖 **schema 与字段语义**,不挖任何 dashboard/存储实现;studio 的 stdlib-http + jsonl 方案继续自研。另两个种子候选踩了雷:phoenix 是 ELv2(非 OSI)+ 专利声明,argilla 官方进入维护模式——都降级。

## 推荐候选(Top 2–3,按价值排序)

### langfuse
- repository: github.com/langfuse/langfuse
- stars: ~30.6k · license: MIT(⚠️ `ee/`、`web/src/ee/`、`worker/src/ee/` 目录为商业 license,挖之前确认文件路径)· 活跃度: 极活跃——v3.205.1 发布于 2026-07-05,606 个 release,YC W23 公司维护
- mined_for:
  - 数据面: **Score 对象 schema**:`id / name / value(数值型) / stringValue(分类·布尔·文本型) / dataType(NUMERIC|CATEGORICAL|BOOLEAN|TEXT) / source(API|EVAL|ANNOTATION) / comment / configId` + **挂载点四选一强校验**(traceId | observationId | sessionId | datasetRunId 恰好一个)。**ScoreConfig schema**:`minValue/maxValue/categories(label-value 对列表)/description/isArchived`。**annotation queue 模型**:queue 绑定 ScoreConfig 定义标注维度,item = 对象引用(trace|observation|session)+ 状态(pending→completed),完成即写 Score。trace/observation 三型(span|generation|event)+ 传播属性(environment/tags/metadata/release/version)。
  - 机制面: ① score 的 `source` 枚举把"谁产生的标签"标准化——judge 产出=EVAL、founder UI 点击=ANNOTATION、外部机器回写=API,比我们现在 `actor: system|founder` 二值更能支撑回流分析;② annotation queue 的"队列绑 config、完成即落分、全键盘导航"交互是"操作即标签"的成熟范式,可指导 studio Decisions 页演进;③ ScoreConfig 让标注维度可配置化(类比新增 `config/labels.json`),UI 标注不再硬编码 star/kill。
- 挖什么: 文档三页数据模型(`langfuse.com/docs/observability/data-model`、`/docs/evaluation/scores/data-model`、`/docs/evaluation/experiments/data-model`——比读源码快且完整);repo 内 `packages/shared/` 下的 Prisma schema(score/score_config/annotation_queue 表定义)与 `fern/` 下的 OpenAPI 定义(scores、annotation-queues 接口的请求/响应 shape);annotation queues 文档页的交互流程描述。
- SKIP 什么: 整个运行时(TypeScript/Next.js/Prisma/ClickHouse/Redis/S3 多服务架构)——v3 自托管需 ClickHouse,与我们非目标直接冲突;`ee/` 目录(商业 license);web UI 组件代码。
- 坑: v2→v3 大版本重构过,搜到的旧博客/旧 self-hosting 文档可能描述 v2 架构;MIT/商业双 license 按目录划分,自动挖矿 skill 必须做路径过滤;文档站与 repo 是两个源,schema 以 repo 的 Prisma/OpenAPI 为准。
- recommendation: adopt
- 理由: score+ScoreConfig+annotation-queue 是全生态最完整、license 最干净的"标注即数据"schema,字段可直接搬进 verdicts.jsonl(给 founder_action 事件补 dataType/configId/comment,给 verdict 记录补 source 枚举)。
- 与硬约束的冲突: 运行时与"无数据库服务"非目标冲突——裁剪方式:只 promote 字段形状与枚举到我们的 jsonl 记录,零依赖零服务;MIT 允许抄 schema 与字段名。

### openinference
- repository: github.com/Arize-ai/openinference
- stars: ~1.1k(spec 仓库,星数不代表权威度——Arize 官方维护,Phoenix 等多产品实现)· license: Apache-2.0 · 活跃度: 活跃,最近 release 2026-07-01,多语言 instrumentation 持续更新
- mined_for:
  - 数据面: `spec/semantic_conventions.md` 的**属性命名表**:`llm.model_name / llm.provider / llm.invocation_parameters / llm.token_count.{prompt,completion,total}` + 细分(`prompt_details.cache_read/cache_write`、`completion_details.reasoning`)、成本镜像 `llm.cost.{prompt,completion,total}`、`retrieval.documents` + `document.{id,content,score,metadata}`、`tool_call.{id,function.name,function.arguments}`。**10 种 span kind**(`openinference.span.kind`):LLM/EMBEDDING/CHAIN/RETRIEVER/RERANKER/TOOL/AGENT/GUARDRAIL/EVALUATOR/PROMPT。
  - 机制面: **扁平 dot-namespace + 零基索引展开**(`llm.input_messages.0.message.role`)——列表不嵌套、一条记录一层平铺,天然适配 jsonl 单行 append,和我们 traces.jsonl 的形状同构。
- 挖什么: `spec/` 目录全部 markdown(semantic_conventions.md 为主,embedding_spans.md 等为辅)。给 traces.jsonl 的 promote 建议:当前 trace 记录是 `{entity_id, prompt_version, request, response, model, ts}`,可对齐补充 `llm.token_count.*`、`llm.cost.*` 字段名(成本梯度第一原则的度量基础——现在 trace 里没有 token/cost,漏斗成本单调性无法验证!)以及给 enrich/diligence 的取证与评审调用打 RETRIEVER/EVALUATOR 类别标。
- SKIP 什么: `python/`、`js/`、`java/`、`go/` 全部 instrumentation 包——都是给 OTel SDK 用的运行时,我们没有 OTel 也不需要。
- 坑: 与 OTel 官方 `gen_ai.*` 约定(open-telemetry/semantic-conventions-genai)并行存在且命名不同(`llm.token_count.prompt` vs `gen_ai.usage.input_tokens`);OTel 版仍处 Development 状态、零 release、字段在 churn——现在钉 OpenInference 的 spec,把 OTel 仓库列为 watch 项,等其 stable 后再评估是否迁移命名。
- recommendation: concepts-borrow
- 理由: 一份纯 markdown 规范、Apache license、字段设计已被多个生产系统验证——是给 traces.jsonl 定字段名时唯一需要读的文档,尤其补上 token/cost 字段直接服务成本梯度的可观测。
- 与硬约束的冲突: 无(借命名,零代码零依赖)。

### label-studio
- repository: github.com/HumanSignal/label-studio
- stars: ~27.8k · license: Apache-2.0 · 活跃度: 活跃——v1.23.0 发布于 2026-03-13,HumanSignal 公司维护
- mined_for:
  - 数据面: **task/annotation JSON 格式**(标注存储的行业事实标准):task 含 `data`(原始内容)+ `annotations[]` + `predictions[]`;annotation 含 `result[]`(与 region id 绑定)、`was_cancelled`(跳过也是标签)、`ground_truth`(黄金标注标记)、`lead_time`(标注耗时秒数)、`completed_by`。
  - 机制面: **predictions(机器预标)与 annotations(人工标注)同构并存**——同一 result schema、不同容器字段,可直接对比算 agreement/校准。这正是我们"system verdict vs founder override"的结构:把 judge verdict 视为 prediction、founder 点击视为 annotation,retro 段即可免费获得"系统预测 vs 人工纠正"的校准数据。
- 挖什么: 文档 `labelstud.io/guide/task_format` 与 `guide/export`(全部字段语义);给 do_label 的 promote 建议:verdicts.jsonl 的 founder 事件补 `lead_time`(founder 犹豫多久——本身是置信度信号)与 `was_cancelled`(跳过/无法判断也记录,比只记 star/kill 的标签覆盖率高)。
- SKIP 什么: Django 全家桶、前端标注组件库、ML backend 集成、企业版文档(docs.humansignal.com 有部分 EE-only 功能)。
- 坑: 文档分社区版(labelstud.io)与企业版(docs.humansignal.com)两站,字段有 EE-only 的;result 的 `value` 结构随标注类型变化(文本/图像/分类各不同),只借顶层 annotation 元数据字段,别陷进 region/value 细节。
- recommendation: concepts-borrow
- 理由: 标注事件的元数据字段(耗时、跳过、黄金标记)与 prediction/annotation 二元结构是十年标注工具生态沉淀的最小完备集,我们的 do_label 目前只记 action 本身,信息量流失。
- 与硬约束的冲突: 无(借字段概念;Django+DB 运行时不碰)。

## 评估过但不推荐(skip 清单,防重爬)

- phoenix(github.com/Arize-ai/phoenix,~10.4k)— skip:**Elastic License 2.0(非 OSI)+ README 专利保护声明**,代码只能看不能抄;其 annotation/span 概念经 Apache 的 openinference spec + 公开文档即可获得,无须登记 ELv2 仓库。
- opik(github.com/comet-ml/opik,~19.7k)— skip:Apache-2.0 但后端是 Java 21 + ClickHouse + MySQL + Redis + MinIO 五件套;trace/span/feedback-score 模型与 langfuse 同构,登记 langfuse 即覆盖,避免重复挖矿。
- argilla(github.com/argilla-io/argilla,~5k)— skip:**官方维护模式**(README 明言原作者已离开、不再加新功能)+ 需 Elasticsearch+PostgreSQL;唯一亮点 suggestion(机器建议)/response(人工回应,含 submitted|discarded 状态)二元结构,已被 langfuse 的 source 枚举 + label-studio 的 predictions/annotations 覆盖。
- otel-genai-semconv(github.com/open-telemetry/semantic-conventions-genai)— skip(暂):Apache-2.0 且是未来行业标准方向,但处 Development 状态、零 release、`gen_ai.*` 字段仍在 churn;列为 **watch 项**,stable 后再钉 commit 并评估从 OpenInference 命名迁移。
- datasette(github.com/simonw/datasette)— skip:以 sqlite 为中心的探索工具;登记它会把 ledger 推向"文件数据库化",与"jsonl 文件即真相"非目标正面冲突(simonw/llm 的"CLI 日志进 sqlite + datasette 浏览"模式记录在此,仅作生态坐标)。
- lnav(github.com/tstack/lnav)— skip:终端日志浏览器(BSD-2),其"JSON log format file 声明字段 + line-format 展示"概念是 jsonl schema 自描述的有趣先例,但 C++ TUI 无 web 漏斗面,无可 promote 资产。
- klp(github.com/dloss/klp)— skip:单作者轻量 CLI 结构化日志查看器,无 schema 资产。
- doccano(github.com/doccano/doccano)— skip:标注工具但活跃度低于 label-studio,同为 Django+DB,完全冗余。
- lmnr(github.com/lmnr-ai/lmnr,laminar)— skip:Apache-2.0 但 ClickHouse+Postgres 后端,数据模型与 langfuse/opik 同构且更年轻,无增量。
- helicone(github.com/Helicone/helicone)— skip:proxy-first 云架构(ClickHouse/Kafka 系),观测靠网关拦截,与我们离线默认路径的形态不符,无文件友好资产。
- langsmith — skip:闭源(LangChain 商业产品),非候选。

## 本 lane 的搜索方法沉淀

- **最高效入口**:官方文档站的 "data model" 页(检索词 `<product> data model trace score schema`)。langfuse 的三页数据模型文档信息密度远高于读源码;先读 docs 再定位 repo 内 schema 文件是正确顺序。
- **license 排雷必做**:`<repo> license` 检索 + 直接看 LICENSE 文件。本 lane 两个雷都靠这个发现:phoenix 的 ELv2、langfuse 的 `ee/` 目录分层 license。**同一公司 spec 仓与产品仓 license 可以不同**(openinference Apache vs phoenix ELv2)——挖 spec 不挖产品是合法路径。
- **维护状态**:直接 WebFetch GitHub 仓库页看最新 release 日期与 README 声明,argilla 的 maintenance-mode 声明就写在 README 里,搜索引擎摘要不会告诉你。
- **死胡同**:"lightweight funnel dashboard jsonl no database"方向搜不到 web 先例——LLM 可观测生态清一色 ClickHouse/DB 后端,文件派只有终端工具(lnav/klp)与 sqlite 派(datasette)。未来 miner skill 在本 lane 应该直奔 schema/字段语义(docs data-model 页 + prisma/openapi 文件),不要再花时间找"无数据库 dashboard"对标物。
