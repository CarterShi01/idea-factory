---
doc: research
lane: L6
title: "diligence：LLM-as-judge 与对抗评审"
date: 2026-07-07
agent: subagent
---

# L6 diligence：LLM-as-judge 与对抗评审

## 结论速览

推荐 **promptfoo**（工业级 judge prompt 库，MIT，OpenAI 官方 evals 迁移指定目的地）、**deepeval**（G-Eval 两段式 + DAG 决策树评审，Apache-2.0，与我们"确定性代码包住 LLM 字段"第一原则同构）、**verdict**（judge 协议分类学白皮书 + 分层验证原语，MIT，concepts-borrow）。

最重要的发现有两个：

1. **我们的 enforce_citation 有公开先例**——google-deepmind/long-form-factuality 的 SAFE（每条 claim 必须被检索结果支持，引不出即判 not-supported）与我们"kill 引不出真实 evidence id 就降级 review"是同一机制的两个实例；promptfoo 的 `DEFAULT_AGENT_GRADING_PROMPT`（评审可调用工具取证再裁决）是它的 agentic 变体。这条路线是业界共识方向，我们已领先落地，不必推倒重来。
2. **业界可靠性工程的主流手段清单**（位置交换、分类裁决代替连续打分、CoT 步骤锚定、强制 JSON reason 字段、长度纪律反 verbosity bias）我们已实现大半；剩余最大增量是 deepeval 的"评分步骤显式锚定（固定 evaluation_steps 提高重跑一致性）+ 前置二值判定 DAG"和 promptfoo factuality 的"枚举分类（A–E）代替数值分"。位置偏差对我们威胁较小——我们是逐条绝对评分而非 pairwise 比较，但 batch 内 forced distribution 排序仍要警惕分数不可比问题。

另注：**openai/evals 已进入退役倒计时**（平台 2026-10-31 只读、2026-11-30 关停），OpenAI 官方迁移指引指向 promptfoo（promptfoo 于 2026-03 被 OpenAI 收购）——种子清单里的 openai/evals 应直接由 promptfoo 取代。

## 推荐候选（Top 2–3，按价值排序）

### promptfoo
- repository: github.com/promptfoo/promptfoo
- stars: ~22.4k · license: MIT · 活跃度: 非常活跃（255 contributors，持续 release；2026-03 被 OpenAI 收购，OpenAI evals 平台退役后的官方迁移目的地）
- mined_for:
  - 数据面: `src/prompts/grading.ts` 里 7 个成品评审 prompt 文本——`DEFAULT_GRADING_PROMPT`（rubric→`{reason, pass, score}` JSON 契约）、`PROMPTFOO_FACTUALITY_PROMPT`（A–E 五档枚举分类裁决：子集一致/超集一致/完全一致/矛盾/非实质差异——分类比打分稳的范本）、`OPENAI_CLOSED_QA_PROMPT`（逐步推理后只输出 Y/N 单字符）、`SELECT_BEST_PROMPT`（多候选比较返回索引）、`DEFAULT_AGENT_GRADING_PROMPT`（评审带工具取证 + 不可信材料防注入警告）；`src/prompts/index.ts` 里 `GEVAL_PROMPT_STEPS`/`GEVAL_PROMPT_EVALUATE`
  - 机制面: rubric 当 config 不当代码（我们 `config/llm/*.json` 已同构）；"枚举裁决代替数值分"可用于 evidence↔claim 一致性判定；agentic grading 的防 prompt injection 段落值得抄进我们把外部证据文本喂给 judge 的 user_template
- 挖什么: `src/prompts/grading.ts`（全部评审 prompt 正文）、`src/prompts/index.ts`（G-Eval 两条 prompt）、`site/docs/configuration/expected-outputs/model-graded/*.md`（judge 最佳实践与 rubric 写法文档，含 bias 提示）
- SKIP 什么: 整个 TypeScript 运行时、provider 适配层、red-team/渗透模块、Web UI、CI 集成——全部与我们无关，只挖 prompt 文本与文档
- 坑: 仓库巨大（评估+红队+UI 混装），挖矿要钉住 `src/prompts/` 一个目录；被 OpenAI 收购后路线可能向 OpenAI 生态倾斜，钉 commit 镜像尤其必要；prompt 更新频繁，镜像会漂移
- recommendation: adopt（prompt 资产级 adopt，运行时零引入）
- 理由: 业界被验证最广（OpenAI/Anthropic 都在用）的评审 prompt 文本集合，MIT 可直接改写进我们的 critique/judge，单文件可挖。
- 与硬约束的冲突: 无（只借 prompt 文本，不引依赖不联网）。**提醒**：借鉴改动 critique/judge prompt 时，正文锁在 `dify/flows/*.yml`，`config/llm/*.json` 是镜像，两处必须同步（CI 有 `test_dify_mirror_invariant.py` 钉）。

### deepeval
- repository: github.com/confident-ai/deepeval
- stars: ~13k · license: Apache-2.0 · 活跃度: 非常活跃（高频 release，300 万月下载，Confident AI 公司维护）
- mined_for:
  - 数据面: `deepeval/metrics/g_eval/template.py`——G-Eval 两段式模板（criteria→自动生成 3–4 条 evaluation steps→按 steps 打分，返回 `{steps:[...]}`/`{score, reason}` JSON）；rubric 参数的分数区间锚定写法
  - 机制面: ① **固定 evaluation_steps 提高重跑一致性**——传入显式 steps 就跳过 CoT 生成步，评分方差显著下降：可直接提案把我们 judge 五维的评分动作写成显式编号步骤（现在是维度定义+锚点，缺"先做什么后做什么"）；② `deepeval/metrics/dag/` 的决策树评审（TaskNode/BinaryJudgementNode/VerdictNode，廉价二值判定在前、贵的 G-Eval 只在特定分支运行）——与我们 gate→critique→judge→enforce 同构且完全对齐成本梯度，其"VerdictNode 子节点才挂贵 metric"的表达可借来把 gate 规则显式化为可配置树；③ G-Eval 的 token 概率加权得分（logprob weighted summation）——若后端暴露 logprobs，可作 confidence 校准的旁路信号
- 挖什么: `deepeval/metrics/g_eval/`（template.py + schema 定义）、`deepeval/metrics/dag/`（节点类型与图执行语义，读懂即可，不抄运行时）、docs 站 `metrics-llm-evals`/`metrics-dag` 两页（设计动机说明比代码更值钱）
- SKIP 什么: pytest 集成、Confident AI 云平台对接、synthesizer/数据集模块、telemetry（deepeval 带 opt-out 遥测，绝不引运行时）
- 坑: 框架迭代快、模块路径历史上重构过（老博文的 import 路径已失效，以 main 分支为准）；文档大量导流其云产品，注意剥离营销内容
- recommendation: adopt（G-Eval 模板与 DAG 表达借入；运行时零引入）
- 理由: G-Eval 步骤锚定与 DAG 前置判定是我们 judge 一致性和 gate 显式化的最短升级路径，Apache-2.0 可抄。
- 与硬约束的冲突: 无（借模式抄纯函数级别）。DAG 若照搬"每节点一次 LLM 调用"会增加便宜段调用次数——裁剪方式：二值判定节点尽量用确定性代码（我们 gate.py 已是），只有语义分支才花 LLM 钱。

### verdict
- repository: github.com/haizelabs/verdict
- stars: ~0.4k · license: MIT · 活跃度: ⚠️ 单团队（Haize Labs）研究向库，v0.2.1 发布于 2025-02，近一年活跃度存疑（commits 页未能确认 2026 有更新）——按"论文配套精品"对待而非活项目
- mined_for:
  - 数据面: 无（prompt 内联在 pipeline 示例里，不成体系）
  - 机制面: ① judge 协议**分类学**（whitepaper.pdf + docs/concept/：verification 分层、debate→aggregate、ensemble+MaxPool 投票等原语及其在 safety/hallucination/reward 任务上哪种组合实证有效）——我们 critique→judge→enforce 本质是一条手写的 Verdict pipeline，用它的分类学审视自己的架构缺了哪块（最值得提案的一块：judge 之后加一层**便宜 verifier 检查 judge 理由与证据是否自洽**，即 enforce_citation 的 LLM 加强版，只对 kill/pursue 边界样本启用）；② `CategoricalJudgeUnit` + `BooleanScale`/`DiscreteScale` 的 scale 设计——再次印证"离散分类优于连续分数"
- 挖什么: `verdict.haizelabs.com/whitepaper.pdf`（核心资产，协议组合的实证结论）、`docs/concept/*.md`、`verdict/` 下 unit 原语的接口定义（只读签名，不抄执行器）
- SKIP 什么: 执行器/并发调度、DSPy 与 provider 集成、notebooks（75% 是 Jupyter，跑起来才有用的部分全跳过）
- 坑: 项目可能已停止维护；"judge-time compute scaling"的默认姿态是堆推理 token，照搬会炸成本
- recommendation: concepts-borrow
- 理由: 唯一把 LLM-as-judge 研究文献做成"可组合原语目录"的库，白皮书是 diligence 段架构演进的最佳对照表。
- 与硬约束的冲突: 与成本梯度第一原则有张力（诱导对所有样本加评审算力）——裁剪方式：额外的验证层/辩论轮只对 diligence 幸存者中的裁决边界样本（分数接近阈值、或 kill 但证据丰富的）启用，批量样本维持现有单轮 critique+judge。

## 评估过但不推荐（skip 清单，防重爬）

- openai-evals（github.com/openai/evals）— skip：平台 2026-11-30 关停、仓库停止更新，官方迁移指引指向 promptfoo；其经典 modelgraded prompt（fact/closedqa）已被 promptfoo `grading.ts` 吸收，挖 promptfoo 即可。
- prometheus-eval（github.com/prometheus-eval/prometheus-eval）— skip：核心是微调评审模型（7B/13B 权重），与我们 API-judge 路线无关且活跃度停在 2024；唯一资产"score rubric schema"（criteria + 每档 1–5 分的文字描述 + reference answer）读 `libs/prometheus-eval/prometheus_eval/prompts.py` 一眼即可吸收——我们五维 0/0.5/1 锚点已是同款思想。
- thunlp-chateval（github.com/thunlp/ChatEval）— skip：论文配套代码 ~300 stars，2023 年后停更，架在过时的 FastChat 上；多角色辩论评审的思想已被我们 critique(advocate)+judge 实现，增量辩论轮的收益按 ICLR 2025 复现研究（"Should we be going MAD?"）证明边际且贵。
- skytliang-multi-agents-debate（github.com/Skytliang/Multi-Agents-Debate）— skip：MAD 原始论文代码，停更；"tit-for-tat 多轮辩论"直接违反成本梯度（对每条 idea 多轮多 agent），且复现研究显示对评审质量增益不稳。
- baaivision-judgelm（github.com/baaivision/JudgeLM）— skip：微调 judge 模型（训练+权重路线），我们不训模型；其"swap augmentation/reference support"训练技巧对 API-judge 只剩概念价值，survey 里读结论即可。
- weopenml-pandalm（github.com/WeOpenML/PandaLM）— skip：同上，微调 judge 模型，2023 年项目基本停更。
- cshaitao-awesome-llms-as-judges（github.com/CSHaitao/Awesome-LLMs-as-Judges）— skip（作为注册源）：纯论文清单无代码资产，且更新停在 2024-12；但作为**检索入口**价值高（bias/calibration 章节的论文索引全），记入搜索方法而非 sources.yaml。
- sksoumik-llm-as-judge（github.com/sksoumik/llm-as-judge）— skip：单作者小型实验仓；其 S1–S6 去偏策略清单（位置交换/同模型集成/跨模型集成/校准 rubric/强制 CoT/参照引导）可当一页 checklist 读完，不值得登记为源。
- lechmazur-position-bias（github.com/lechmazur/position_bias）— skip：单作者的 judge 位置偏差 benchmark，对逐条绝对评分（我们的模式）不适用，pairwise 场景才需要。
- google-deepmind-long-form-factuality（github.com/google-deepmind/long-form-factuality）— skip（登记为先例引用而非挖矿源）：SAFE 是"引证强制"最权威公开先例（claim 拆分→逐条检索支持→不支持即判负），但代码是绑 Google Search 的一次性研究工程，2024 后停更；结论已吸收进本报告，无需再爬。

## 本 lane 的搜索方法沉淀

- **最有效入口**：① 直接搜 `<项目名> + github + license + 活跃度` 再 WebFetch 仓库首页验证 stars/release 日期——搜索摘要的 stars 数经常过时或张冠李戴（"verdict"一词撞名严重，必须带 org 名 haizelabs 检索）；② 搜产品文档站（promptfoo.dev、deepeval.com 的 docs 页）比搜 GitHub 更快定位"prompt 正文在哪个源文件"，再直接 WebFetch 该源文件路径。
- **高产检索词**："LLM-as-a-judge position bias sycophancy self-preference mitigation"（一次带出去偏策略全景）、"judge-time compute scaling"（带出 verdict 及其白皮书）、"model-graded eval prompts"（带出 promptfoo grading 资产）。
- **死胡同**：① multi-agent debate 方向整体是 2023–2024 论文代码坟场（ChatEval/MAD 及各复刻全部停更），思想早被吸收进商用框架，别再逐仓爬；② 微调 judge 模型系（JudgeLM/PandaLM/Prometheus）与 API-judge 管线正交，只有 survey 价值；③ 泛搜"adversarial review prompt"噪音极大，法庭范式（advocate vs judge）没有独立成熟开源仓——它在业界的形态就是 promptfoo/deepeval 这类框架里的一个 grading 配置，或 verdict 里的一个 pipeline 组合。
- **给未来 miner skill 的提示**：本 lane 的资产高度集中在单文件（promptfoo `src/prompts/grading.ts`、deepeval `metrics/g_eval/template.py`、verdict whitepaper.pdf），镜像时按文件钉 commit 即可，不需要整仓浅克隆。
