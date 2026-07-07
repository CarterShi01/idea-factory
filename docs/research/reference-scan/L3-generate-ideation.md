---
doc: research
lane: L3
title: "generate:LLM 想法/假设生成"
date: 2026-07-06
agent: subagent
---

# L3 generate:LLM 想法/假设生成

## 结论速览

Top 3:**noviscl-ai-researcher**(MIT,斯坦福"Can LLMs Generate Novel Research Ideas?"官方仓,过量产出→去重→锦标赛→过滤的完整范式,prompt 可直接抄)、**sakana-ai-scientist**(14k+ stars,反思回路/想法存档防重/新颖性工具回路三个机制极可借,但 license 非标只能借概念)、**chats-lab-verbalized-sampling**(Apache-2.0,我们已在用 VS,登记为持续跟踪源以校准 k/tau 与任务变体)。

**最重要的发现**:"信号→商业点子"的成型 prompt 在开源界**没有高质量范例**——搜到的全是单页浅模板(如 jamesponddotco 的 business-idea-generator.md)或闭源 SaaS;最高质量的"过量产出→筛选"工程都在学术 ideation 仓库里,且其流水线形状(generate → embedding 去重 → 排序 → novelty/feasibility 过滤)与我们 generate→triage→rank 漏斗**完全同构**,可放心移植范式。我们现有 `config/llm/generate.json`(VS + probability + 反模板硬禁 + 三源分叉 + fusion)在"商业点子"这个细分上已领先开源现状;要补的是**批内防重与新颖性回路**这两块机制。

次要发现:学术 ideation 仓库普遍用"LLM pairwise 排序"(Swiss tournament / Idea Arena),这与我们"rank 段纯代码因子"铁律冲突——借它们的实证结论(pairwise > 直接打分)到 diligence 段即可,不要把 LLM 排序引入 rank 段。

## 推荐候选(Top 2–3,按价值排序)

### noviscl-ai-researcher
- repository: github.com/NoviScl/AI-Researcher
- stars: ~0.4k · license: MIT · 活跃度: 研究配套代码,论文(2024-09,arXiv:2409.04109)发表后基本冻结;单一维护者(Chenglei Si,Stanford)。停更不影响挖矿——资产是静态 prompt 与算法,但别指望上游演进。权威度远高于 star 数:该论文是"LLM 能否产出新想法"领域最高引用的人评研究(79 位专家盲评),仓库是其全部实现。
- mined_for:
  - 数据面: `ai_researcher/src/grounded_idea_gen.py` 内嵌的想法生成 prompt 架构(RAG grounding 段 + demo 示例 + "avoid repeating the following existing ideas" 防重护栏,把已生成想法的**短名列表**回填进 prompt);`filter_ideas.py` / `novelty_check.py` 的 novelty/feasibility 过滤 prompt;`tournament_ranking.py` 的 pairwise 比较 prompt("Directly return a number 1 or 2 and nothing else")。MIT,prompt 文本可直接抄改。
  - 机制面: 完整的"过量产出→筛选"四段:①按 topic 批量生成(temperature=1.0,每次 5 条,累积数千条 seed ideas);②embedding 余弦 0.8 阈值去重(`dedup_ideas.py`/`analyze_ideas_semantic_similarity.py`);③Swiss 锦标赛 pairwise 排序(5 轮,按积分配对,`tournament_ranking.py`);④novelty/feasibility 过滤。论文实证:pairwise 比较显著优于让 LLM 直接打分——这条结论可迁移到我们 diligence 段的 judge 设计。
- 挖什么: `ai_researcher/src/grounded_idea_gen.py`(生成 prompt 全文 + 防重护栏写法)、`dedup_ideas.py` + `analyze_ideas_token_similarity.py`(后者是 token/n-gram 相似度版去重,**可改写成纯 stdlib 函数**给我们的批内去重)、`tournament_ranking.py`(配对与积分逻辑约 100 行纯逻辑)、`filter_ideas.py`(过滤 rubric prompt)、`self_improvement.py`(自我改进一轮的 prompt 措辞)。
- SKIP 什么: `lit_review*.py`(Semantic Scholar 检索,属 L5 enrich 场景且需联网 API);`execution_*` / `experiment_plan_gen.py`(学术实验执行,与我们无关);`reviews_*` 目录(人评研究数据)。
- 坑: ①去重用 sentence-transformers embedding,是非 stdlib 依赖——裁剪为我们已有的 dedup 逻辑或 n-gram 相似度纯函数,语义级留给便宜 LLM pair 判定;②prompt 是学术 idea 措辞("expert researcher in AI"、五段式 Problem/Method/Experiment),字段要换成我们的商业 schema,抄的是**骨架**(grounding→示例→防重列表→格式强制)不是正文;③论文自己的后续研究(arXiv:2506.20803)发现 LLM ideas 执行后评分显著回落——正好印证我们"generate 过量产出、evaluation 负责杀"的分工,不要指望生成侧 prompt 解决质量问题。
- recommendation: adopt
- 理由: 与我们漏斗完全同构的、有大规模人评背书的过量产出→筛选实现,MIT 可直接抄 prompt 骨架与去重/排序纯函数。
- 与硬约束的冲突: ①Swiss 锦标赛=让 LLM 做排序,直接违反"rank 段纯代码因子"铁律——裁剪:不进 rank 段;只把"pairwise > 直接打分"结论借给 diligence 段的 judge 流程,或在 generate 批内做一次便宜小模型 pairwise 预筛(成本梯度允许:早段便宜钱);②embedding 去重依赖 sentence-transformers,违反 stdlib-only——裁剪为 n-gram/词法相似度纯函数 + 便宜 LLM pair 判定(与 L2 lane 的 triage 方案汇合)。

### sakana-ai-scientist
- repository: github.com/SakanaAI/AI-Scientist(v2: github.com/SakanaAI/AI-Scientist-v2)
- stars: v1 ~14.2k / v2 ~6.8k · license: **非标:"The AI Scientist Source Code License"(Responsible AI License 衍生),非 MIT/Apache** · 活跃度: 团队维护(Sakana AI 公司),v1 已进入维护态、v2 为现行版;非单作者。
- mined_for:
  - 数据面: 无(license 非标,prompt 正文不可直接抄;只能用自己的话重写等价结构)。
  - 机制面: 三个高价值机制,全部可用 stdlib+我们现有 LLM 抽象重写:①**反思回路**:每条想法生成后跑 num_reflections 轮自我改进,带早停标记("If there is nothing to improve, simply repeat the previous JSON EXACTLY … include 'I am done'"),文本含 "I am done" 即停——比我们现在一次成型多一道便宜的质量增益,且早停控成本;②**想法存档防重**:`idea_str_archive` 把历史想法 JSON 串接回填进后续生成 prompt("Here are the ideas that you have already generated: …"),实现跨批次防重——我们目前只有 VS 批内多样性,没有跨信号/跨天的生成端防重;③**新颖性检查作为工具回路**:LLM 自己生成检索词→查 Semantic Scholar→多轮(默认 10)后输出显式判决 "Decision made: novel. / not novel."——判决字符串由代码解析,语义判断归 LLM、门归代码,与我们第一原则同构;④自评分字段 Interestingness/Feasibility/Novelty(1-10)与我们的 probability 字段同族,v2 的输入模板(Title/Keywords/TL;DR/Abstract 的 markdown topic 文件)可借作信号包格式参考。
- 挖什么: 只读这三个文件的**结构**:v1 `ai_scientist/generate_ideas.py`(idea_first_prompt / idea_reflection_prompt / novelty_prompt 三段回路的编排方式与 JSON 字段集)、v1 各 template 的 `seed_ideas.json`(少样本示例的组织格式)、v2 `ai_scientist/perform_ideation_temp_free.py`(工具化 ideation 的演进版)。
- SKIP 什么: 实验执行/论文写作/评审全链(`perform_experiments` / `perform_writeup` / aider 集成)——重运行时且与我们无关;v2 的 agentic tree search(为跑实验设计,非 ideation);一切代码复制(license 禁区)。
- 坑: ①license 是 RAIL 衍生的自定义许可,**抄代码/抄 prompt 原文都有风险**,必须概念级重写;②新颖性回路每条想法最多 10 轮检索+判定,单条成本高——若照搬进 generate 段会破坏成本梯度;③reflection 轮数×5 直接把生成段单价乘 5;④依赖 Semantic Scholar 联网 API,默认离线路径不可用。
- recommendation: concepts-borrow
- 理由: 三个机制(反思早停、存档防重、新颖性判决回路)是本 lane 最值得移植的工程模式,但 license 决定只能借概念重写。
- 与硬约束的冲突: ①license 非标→降为 concepts-borrow(已按此定级);②新颖性回路与 reflection 若放 generate 段违反成本梯度——裁剪:reflection 砍到 1 轮或只对高 probability 候选做;新颖性/查重回路后移到 enrich/diligence 段只对幸存者跑,或在 generate 侧退化为"存档防重"这种零额外 LLM 调用的 prompt 内护栏;③Semantic Scholar 联网→离线路径不用,live 为 opt-in。

### chats-lab-verbalized-sampling
- repository: github.com/CHATS-lab/verbalized-sampling
- stars: ~0.8k · license: Apache-2.0 · 活跃度: 2025-10 论文(arXiv:2510.01171)配套官方仓,近期有持续 commit;学术团队维护,规模不大但是 VS 方法的**唯一权威源**。
- mined_for:
  - 数据面: 官方 VS prompt 模板与默认参数(k=5、tau=0.10 概率阈值)、任务别变体(creative writing / synthetic data / dialogue)——我们 `config/llm/generate.json` 已用 VS(3-5 条+probability)但**没有 tau 阈值**(低置信候选现在靠 evaluation 杀而非生成端弃),官方措辞与参数可用来校准我们的 prompt。
  - 机制面: 概率分布口径("给出你对该回答真实概率的估计"的确切措辞影响分布质量)、k 与多样性/质量的权衡数据(论文报 2-3x 多样性增益)。
- 挖什么: `examples/`、`scripts/` 下各任务的实际 prompt 文本;README/论文里 k、tau 的消融结论;后续 release 中的新任务变体。
- SKIP 什么: 它的 Python 框架/CLI 本体(我们只要 prompt 措辞与参数,不需要它的运行时);notebooks(演示性质)。
- 坑: 仓库偏"论文配套",工程化程度一般,prompt 分散在 examples 与 scripts 里没有统一模板目录,挖的时候要跨文件对照论文;star 数据在不同镜像页差异大(92 vs 771),以仓库主页为准。
- recommendation: adopt
- 理由: 我们生成段核心方法(VS)的上游权威源,Apache-2.0 可直接抄措辞,登记后可持续跟踪方法演进(新 tau/k 消融、新任务变体)。
- 与硬约束的冲突: 无(纯 prompt 层资产,零依赖零联网)。

## 评估过但不推荐(skip 清单,防重爬)

- hkuds-ai-researcher(github.com/HKUDS/AI-Researcher)— skip:全自动科研系统,Docker 镜像起步的重运行时,"要跑起来才有价值",违反 glue-only/只挖不跑;ideation 只是其中薄薄一层,不如 NoviScl 仓直接。
- agent-laboratory(github.com/SamuelSchmidgall/AgentLaboratory)— skip:重心在自动写代码跑实验的执行链,ideation 模块薄,对本 lane 无独有资产。
- coi-agent(github.com/DAMO-NLP-SG/CoI-Agent)— skip(备选):Apache-2.0、509 stars、prompt 在 `prompts/` 目录可读,但核心资产是学术文献链构建(需 Grobid/Java 11 重依赖),与"信号→商业点子"错位;其 Idea Arena 评审与 NoviScl 的 tournament 同构,择一即可。若未来要第二个 pairwise 评审参照可回捞。
- nova-iterative-planning(arXiv:2410.14255)— skip:论文(Plan-Retrieve-Search 提升新颖性 3.4x)值得读,但未见官方开源代码仓,无可登记的源。
- storm(github.com/stanford-oval/storm)— skip:任务错位(检索式长文写作);其 perspective-guided questioning 的多样性思想与我们三源分叉/VS 已重叠,不值得单独登记。
- jamesponddotco-llm-prompts(github.com/jamesponddotco/llm-prompts)— skip:business-idea-generator.md 是单页浅模板,无方法论、无流程、无 schema;同类"brainstorm prompt 库"(awesome-prompt-engineering 等)普遍如此,整个方向判死胡同。
- genspark 及同类 ideation SaaS — skip:闭源产品,无可挖仓库。
- google-deepmind-ai-co-scientist — skip:闭源(仅博客/论文),开源复刻尚无权威实现。
- 各 awesome 列表(HKUST-KnowComp/Awesome-LLM-Scientific-Discovery、Superbooming/Awesome-scientific-idea-generation、Paureel/LLM-SCI-GEN)— skip as source:是入口不是源,无可 pin 的资产;已沉淀到下面的搜索方法。

## 本 lane 的搜索方法沉淀

- **最有效入口**:①锚定标志性论文再找官方仓("Can LLMs Generate Novel Research Ideas" → NoviScl/AI-Researcher),论文背书弥补 star 数偏低的判断噪声;②raw.githubusercontent.com 直读单个 .py 文件(如 generate_ideas.py、tournament_ranking.py),一次 fetch 即可拿到 prompt 骨架与算法细节,比翻仓库页面高效得多;③awesome 列表(HKUST-KnowComp/Awesome-LLM-Scientific-Discovery、Paureel/LLM-SCI-GEN)适合做候选普查,但要逐个验证 license 与活跃度。
- **有效检索词**:"LLM research ideation diversity novelty github"、"hypothesis generation LLM code"、精确短语+作者/机构名(如 "CoI-Agent" DAMO)。
- **死胡同**:①"startup/business idea generation LLM github"——只捞到浅模板、LLMOps 平台和 awesome 堆,商业 ideation 无高质量开源,未来 miner 不必再爬此方向;②追 SaaS 产品(GenSpark 类)找开源实现——无果;③论文有亮点但无代码(Nova、Scideator 多数)——先查有无官方仓再投入阅读。
- **License 教训**:明星仓不等于可抄——SakanaAI 两个仓都是 RAIL 衍生自定义许可,**登记源时 license 必须逐仓核验 LICENSE 文件**,不能凭"开源"印象默认 MIT/Apache。
