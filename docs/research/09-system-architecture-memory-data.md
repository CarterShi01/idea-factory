# 从离线 demo 到"每日产出"系统：架构、记忆与数据设计调研

> 调研层面：**系统架构、记忆与数据设计**。目标是把现有 `idea-factory`（离线 demo + opt-in `collect.py`）和空仓 `idea-evl` 演进成一套**每天稳定产出 10~20 条经过初筛的创业 idea** 的系统。约束：一人公司可维护、stdlib 优先、与现有 `src/` 布局兼容、不引入 Web UI / 数据库服务 / 多 agent 框架（见 `docs/project-brief.md` 非目标）。

## 1. 现状盘点（代码事实）

读过 `collect.py` / `pipeline.py` / `match.py` 后，现有资产已经比想象中接近目标：

- **统一信号 schema 已存在**：`collect._blank_record()` 给出了所有源共享的记录骨架（`id / name / tagline / description / url / categories / target_users / pain_points / launched_at / source / collected_at`）。这是后续一切的地基。
- **多源采集 + 容错已就位**：`collect_all()` 用 `try/except` 隔离每个源的失败，单源挂掉不影响整体——这正是生产管线该有的属性。
- **id 已具确定性**：`_stable_id()` 用 `sha256(seed)[:8]` 给无 id 的项生成稳定 id——**这是做去重/"已见过"判定的天然主键**。
- **stdlib 调度器雏形**：`run_scheduled()` 已实现一个可注入 `sleep`、可限定 `iterations` 的纯 stdlib 定时循环。
- **关键词匹配**：`match.py` 做新信号与已有 idea 的 keyword overlap。

**缺口**：没有持久化的"已见过"状态（每次 collect 都是全量 `save_collected` 覆盖 `data/raw/collected.json`），没有语义去重，没有 idea 候选的稳定存储与状态机，没有人审回流，没有成本/可观测埋点。下面逐项给方案。

## 2. 目标数据流（文字图）

```
[外部事件源]   [脑海 idea 录入]   [模拟痛点分析]
  collect.py      inbox.jsonl       persona prompts
      \               |                 /
       \              |                /
        v             v               v
   ┌──────────────────────────────────────┐
   │  归一化 → 统一信号 schema (含 dedup_key)│  normalize.py(扩展)
   └──────────────────────────────────────┘
                     │
          ┌──────────┴───────────┐
          v                      v
   ┌─────────────┐        ┌──────────────────┐
   │ 精确去重     │        │ 语义去重/"已见过" │  state.db (sqlite + sqlite-vec)
   │ id/hash 命中 │───────>│ KNN cosine < τ ? │
   └─────────────┘        └──────────────────┘
                     │ (仅"新"信号通过)
                     v
   ┌──────────────────────────────────────┐
   │  生成 idea 候选 (generate.py + LLM)    │ → 写 idea_candidates 表
   └──────────────────────────────────────┘
                     │
                     v
   ┌──────────────────────────────────────┐
   │  前期评估打分 (idea-evl)               │ → score/rationale 回写候选
   └──────────────────────────────────────┘
                     │  按分阈值路由
          ┌──────────┴───────────┐
          v (高分)               v (中分/不确定)
     auto-keep            ┌─────────────────┐
                          │ 人审队列 (HITL) │  review_queue.jsonl
                          └─────────────────┘
                                  │ approve/reject/edit
                                  v
                        feedback.jsonl (回流：调阈值/调 prompt/做 eval)
```

每一步都把"贯穿全程的 trace"写进 `runs.jsonl`（一次每日运行 = 一条 run 记录 + N 条 span），用于成本与可观测。

## 3. 定时调度：不要只靠 GitHub Actions cron

调研结论很明确：**GitHub Actions 的 cron 不适合作为唯一的可靠每日触发器**：

| 问题 | 事实 | 来源 |
|---|---|---|
| 漂移 | schedule 不保证准点，高峰期可延迟数分钟到数十分钟 | GitHub 社区/CronSignal |
| 60 天自动停用 | 仓库 60 天无 commit/issue/PR 等"活动"，scheduled workflow 被**静默禁用**（workflow 自己跑不算活动），只发一封容易漏掉的邮件 | GitHub Issue #50 / community #32197 |
| 时区 | cron 一律按 UTC，不是本地时间 | 同上 |

**建议（分层兜底）**：

1. **主调度**用 GitHub Actions `schedule`（免费、与现有 `.github/workflows/claude.yml` 同生态），但加两道保险：
   - 用 `efrecon/gh-action-keepalive` 或一个每 50 天提交 noop 的 workflow 防止被禁用；
   - workflow 末尾写一条"心跳"到仓库（commit `data/processed/last_run.txt` 或调用外部 healthcheck，如 healthchecks.io 的 ping URL），**没收到心跳就告警**——这把"静默失败"变成"可观测失败"。
2. **保留 `run_scheduled()` 作为本地/VPS 兜底**：在任意一台常开机器上 `idea-factory daily --loop` 即可，零额外依赖。业界一人公司常见模式正是"一个 thin 入口，每次只做一个时间窗口的工作，由外部时钟驱动"（见 Crontap/indie-hacker 模式）。
3. **触发即一次性**：每次 run 只处理"自上次水位线以来"的新数据（incremental + watermark），天然幂等，重跑安全。

## 4. 统一信号 schema + 去重/"已见过"判定（核心）

### 4.1 三层去重（成本从低到高，逐层放行）

数据工程与向量库社区的共识是**分层去重**，与训练数据去重同理：

1. **精确层（hash/id）**：用现有 `_stable_id` 或 `sha256(url||title)` 做主键，命中即丢弃。免费、O(1)。
2. **近似层（可选）**：MinHash/LSH 或 `simhash` 抓"几乎一样、仅格式差异"的项。纯 Python 可实现，无外部服务。
3. **语义层（embedding + KNN）**：对真正要不要"算见过"的边界情况，用 embedding 余弦相似度判定 `sim > τ`（如 0.85）即视为"已见过"。

### 4.2 向量库选型：**sqlite-vec**

调研下来，对一人公司、stdlib 友好的最佳选择是 **sqlite-vec**（`pip install sqlite-vec`）：

- 纯 C、无外部依赖、**文件型**，加载为 SQLite 扩展即可，"消除了 Pinecone/Weaviate/FAISS 这类基础设施"；
- 支持 `float32 / int8 / bit` 向量，KNN 支持 L2 / cosine / Hamming；
- 官方定位"单机几万条 embedding 绰绰有余"——每天 10~20 条 idea、几百条信号，**量级完全够用且有数年余量**；
- **风险提示**：sqlite-vec 仍是 pre-v1（最新 v0.1.9），"expect breaking changes"。因此把它**封装在一个 `memory.py` 模块后面**（接口 `seen(record) -> bool` / `remember(record)`），日后换 `numpy` 暴力 KNN 或换库时不影响上层。前期甚至可以**先不上 sqlite-vec**：几百条 embedding 用 `numpy` 算余弦完全够，零新依赖。

它同时充当**记忆层**：`state.db` 里存信号向量、idea 向量、"已见过"水位线，既做去重又支持"这条新事件和你 3 个月前某条 idea 语义相关"的 recall（比 `match.py` 的纯关键词更强，可作为 `match.py` 的语义升级版而非替换）。

### 4.3 schema 演进建议（向后兼容）

在现有 `_blank_record` 基础上**追加而非修改**字段：

| 新字段 | 用途 |
|---|---|
| `dedup_key` | 精确去重主键（hash） |
| `embedding_id` | 指向 `state.db` 中的向量行 |
| `origin` | 三源标记：`external` / `inbox`（脑海 idea）/ `persona`（模拟痛点） |
| `first_seen_at` / `last_seen_at` | 同一信号反复出现时维护，支撑"热度上升"信号 |

## 5. idea 候选存储与状态机

用 **SQLite 单文件**（stdlib `sqlite3`，不违反"不引入数据库服务"——它是嵌入式文件，等价于读写 JSON，但带索引和并发安全）保存 `idea_candidates`：

```
id, created_at, origin, source_signal_id,
pitch, category, target_audience, pain_point,
evl_score, evl_rationale,
status,        -- new → scored → review → kept / rejected
reviewed_by, reviewed_at, edit_note
```

`status` 是一个显式状态机（数据工程里的"review queue 即 workflow state：pending/approved/rejected 驱动下游自动化"）。`export.py` 仍可从该表导出每日 Markdown 摘要给人看。**若坚持极简**，整张表可降级为 `data/processed/candidates.jsonl`（append-only + 末尾状态字段），但建议用 sqlite，因为去重和"按状态查询待审"用 SQL 一行搞定。

## 6. 人审回流（Human-in-the-Loop）

调研到的成熟 HITL 模式（Redis 博客 / Galileo / MongoDB）高度一致，可直接落地为**无 UI 的文件队列**：

1. **置信度/风险路由**：不是所有候选都进人审。`idea-evl` 打分后，**高分 auto-keep，仅"不确定区间"或高风险类目进队列**。务必校准阈值匹配自己的日审能力——"你一天能审 100 条、agent 产 1000 条，那 review 路由率最多 10%"。对一人公司就是：每天最多审 10~20 条。
2. **队列即状态**：`review_queue.jsonl` 每行一条 `pending` 候选 + 恢复所需的完整上下文（信号、pitch、评分、rationale）。审完把决定写回候选表的 `status`。
3. **反馈回流闭环**：每个人审决定（approve/reject/edit + 理由）落 `feedback.jsonl`。这是**最值钱的数据**——业界做法是"人审产出 → 变成更好的 eval、更好的阈值、更安全的行为"。具体回流三条路径：
   - 调 `idea-evl` 的**打分阈值**；
   - 把 reject 案例做成 `idea-evl` 的 **few-shot 负例 / eval 集**；
   - 用 reject 的语义向量做"**反向去重**"：未来生成的候选若与历史 reject 高度相似，直接降权。

## 7. 成本、限流与可观测（一人公司够用的最小集）

LLM 可观测社区的最小可行实践，全部可用 stdlib（`logging` + JSONL）实现，**无需引入 LangSmith/Datadog**：

- **每次 LLM 调用都记 input/output/token/latency/model/cost**，写 `runs/<date>.jsonl`。token×单价即成本，这是"账单→预算"的基础。
- **代理/网关模式**：把所有 LLM 调用收敛到一个 `llm_client.py` 单点，在那里统一记录、重试、限流——而不是散落各处。这与 CLAUDE.md "保持 `cli.py` 薄、逻辑下沉"的风格一致。
- **预算闸**：每日 token/费用上限（如"单日 $X 即停"），防止 prompt bug 导致跑飞——业界明确建议"按天/按用户设配额防 runaway"。
- **限流**：对外部源（HN/PH/RSS）已有 `HTTP_TIMEOUT`；对 LLM API 加简单令牌桶或 `time.sleep` 退避即可。
- **可观测三件套**：run 级 trace（一次每日运行）、span 级（每个 stage）、健康心跳（见 §3）。出问题时 `grep` JSONL 就能定位是哪个源/哪步挂了。

## 8. 对 idea-factory / idea-evl 的具体借鉴与可落地建议

**对 idea-factory（增量、不破坏离线 demo）**：

1. **新增 `memory.py`**，对外暴露 `seen(record)->bool` / `remember(record)` / `recall(text, k)`，内部先用 `numpy` 余弦（零新依赖），量大再切 sqlite-vec。把 `match.py` 的关键词匹配保留为快路径、`memory.recall` 为语义慢路径。
2. **`collect.py` 改增量**：`save_collected` 从"全量覆盖"改为"先经 `memory.seen` 过滤再 append"，并维护每个源的 `last_seen` 水位线，使每日 collect 幂等。
3. **`_blank_record` 追加** `dedup_key / origin / first_seen_at`（向后兼容，老数据缺字段时默认填充）。
4. **新增 `daily` 子命令**：串起 collect → dedup → generate → (调用 idea-evl) → 路由 → 导出，复用现成的 `run_scheduled()` 做本地兜底循环。
5. **保留离线契约**：`daily` 是 opt-in（像 `collect` 一样），默认 `idea-factory` 仍全程离线，不违反非目标。
6. **接入三源**：`origin=external` 走 `collect`；`origin=inbox` 读一个 `data/raw/inbox.jsonl`（用户随手记 idea）；`origin=persona` 用固定 persona prompt 生成"模拟痛点"信号。三者归一到同一 schema 后共用下游。

**对 idea-evl（空仓，从第一行就定好接口）**：

1. **定义稳定 I/O 契约**：输入 = idea-factory 的候选 dict（同 schema），输出 = `{score, rationale, risk_flags, route}`。两仓通过**文件/SQLite 交换**，不耦合进程，符合"不引入多 agent 框架"。
2. **打分即路由**：内置 `route ∈ {auto_keep, review, drop}`，由阈值决定，直接喂给 idea-factory 的人审队列。
3. **eval 集驱动**：把 idea-factory 回流的 `feedback.jsonl`（人审 approve/reject）作为 idea-evl 的回归测试集，每次改打分逻辑先跑这套 eval（可挂在 GitHub Actions 上，正好是社区推荐的"nightly eval pipeline"用法）。
4. **LLM-as-a-judge + 人审兜底**：用 LLM 打分但不全信，落到上面的置信度路由，与 HITL 模式对齐。

**最小技术栈（一人公司、stdlib 优先）**：

- 语言/运行：Python ≥3.10，`src/` 布局（沿用现状）
- 调度：GitHub Actions `schedule` + keepalive + healthcheck 心跳；本地用 `run_scheduled()` 兜底
- 存储/记忆：`sqlite3`（stdlib）做候选表 + 队列；向量先 `numpy`，后 `sqlite-vec`（封装在 `memory.py` 后）
- 数据交换：JSONL（信号 / inbox / review_queue / feedback / runs）+ 一个 `state.db`
- LLM 接入：单一 `llm_client.py` 网关，统一记 token/cost、限流、预算闸
- 可观测：stdlib `logging` → JSONL，`grep`/`jq` 即分析
- 依赖原则：仅 `requests`（已有）、`python-dotenv`（已有）、可选 `sqlite-vec` / `numpy`；不引入 web 框架、消息队列、向量数据库服务

## 参考链接

- sqlite-vec（仓库，pip 安装、float32/int8/bit、L2/cosine/Hamming、pre-v1 警告）：https://github.com/asg017/sqlite-vec
- sqlite-vec 工作原理详解：https://medium.com/@stephenc211/how-sqlite-vec-works-for-storing-and-querying-vector-embeddings-165adeeeceea
- Local-First RAG: Vector Search in SQLite：https://www.sitepoint.com/local-first-rag-vector-search-in-sqlite-with-hamming-distance/
- embeddings 做去重检测（Zilliz）：https://zilliz.com/ai-faq/how-do-i-use-embeddings-for-duplicate-detection
- 万亿级数据去重（精确/语义/近似三层，MinHash LSH）：https://zilliz.com/blog/data-deduplication-at-trillion-scale-solve-the-biggest-bottleneck-of-llm-training
- 语义文本去重（Supabase）：https://supabase.com/docs/guides/ai/quickstarts/text-deduplication
- semhash 快速语义去重库：https://github.com/MinishLab/semhash
- HITL 生产监督模式（Redis，含审批门/置信度路由/反馈回流实现细节）：https://redis.io/blog/ai-human-in-the-loop/
- HITL agent 监督最佳实践（Galileo）：https://galileo.ai/blog/human-in-the-loop-agent-oversight
- HITL for AI Agents 最佳实践与 demo（Permit.io）：https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo
- 7 个 agentic 系统设计模式（MongoDB）：https://www.mongodb.com/resources/basics/artificial-intelligence/agentic-systems
- LLM 可观测性最佳实践 2025（Maxim）：https://www.getmaxim.ai/articles/llm-observability-best-practices-for-2025/
- LLM token 用量与成本追踪指南（Worklytics）：https://www.worklytics.co/blog/how-to-track-llm-token-usage-and-cost
- 从账单到预算：按用户追踪 token/成本（Traceloop）：https://www.traceloop.com/blog/from-bills-to-budgets-how-to-track-llm-token-usage-and-cost
- 用 OpenTelemetry 做 LLM 可观测：https://opentelemetry.io/blog/2024/llm-observability/
- 幂等数据管线（Airbyte，watermark/upsert/分区覆盖）：https://airbyte.com/data-engineering-resources/idempotency-in-data-pipelines
- 增量抽取实现：https://oneuptime.com/blog/post/2026-01-30-data-pipeline-incremental-extraction/view
- GitHub Actions cron 不运行的排查：https://cronsignal.io/troubleshoot/github-actions-cron-not-running
- 60 天无活动自动禁用 scheduled workflow（Issue #50）：https://github.com/fischerscode/DockerFlutter/issues/50
- 防止 workflow 被自动禁用（keepalive action）：https://github.com/efrecon/gh-action-keepalive
- 防止 GitHub 暂停 cron 触发器（DEV）：https://dev.to/gautamkrishnar/how-to-prevent-github-from-suspending-your-cronjob-based-triggers-knf
- GitHub Agentic Workflows 博客：https://github.github.com/gh-aw/blog/
- 定时 AI/LLM 任务模式（Crontap）：https://crontap.com/blog/category/ai-llm
- GitHub Actions 跑 LLM eval pipeline（Tenki）：https://tenki.cloud/blog/github-actions-llm-evaluation-pipeline
