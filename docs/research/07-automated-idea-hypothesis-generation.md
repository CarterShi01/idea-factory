本报告聚焦"用 LLM 自动产生研究想法/假设"的学术工作与方法论，目标是为 idea-factory（生成结构化创业 idea 候选）和 idea-evl（评估/打分）提炼出"如何每天稳定产出 10~20 条既多样、又不重复、且新颖度可量化"的可落地方法。

## 一、领域全景：自动化创意/假设生成已被严肃验证

过去两年，"让 LLM 生成新颖科研想法"从演示走向了大规模对照实验，结论对创业 idea pipeline 很有借鉴意义：

- **Sakana AI Scientist / v2**：端到端自动化科研流水线——生成新颖想法→写代码→跑实验→写论文→自动审稿，单篇成本约 15 美元。v2 引入了**基于树搜索（agentic tree search）**的探索策略，并去掉了对人工模板的依赖，使想法生成阶段更通用。这给我们的启示是：idea 生成不应是"一次性 prompt 出 20 条"，而应是**带搜索/回溯的探索过程**。
- **Stanford "Can LLMs Generate Novel Research Ideas?"（Si, Yang, Hashimoto, 2024）**：招募 100+ 名 NLP 研究者做盲评，控制了主题分布与基线。核心发现：**LLM 生成的想法在"新颖度"上显著高于人类专家（p<0.05），但在"可行性"上略弱**。这正是 idea-factory/idea-evl 的核心张力：新颖度容易拉高，可行性需要专门的评估闸门。
- **The Ideation-Execution Gap（2506.20803）**：同一团队的后续研究，让 43 名专家各花 100+ 小时真正执行被随机分配的想法。结论是**执行后 LLM 想法的所有指标（新颖、兴奋、有效、总分）下降幅度都显著大于人类想法，排名甚至反转**。强烈警示：**ideation 阶段的高分会"虚高"，必须有执行/落地视角的二次评估**——这恰恰是 idea-evl 存在的理由。
- **ResearchAgent（NAACL 2025）**：用学术知识图谱 + 跨论文挖掘的实体来增强检索，并用多个 **ReviewingAgent**（其评审标准从真实人类判断中提炼）做迭代修订。这是"生成 + 评审分离、迭代精炼"的范式模板。

## 二、核心难题：mode collapse 与"多样性 ≠ 调高 temperature"

要稳定每天产 10~20 条而不重复，最大敌人是 **mode collapse**（生成逐渐变得重复、平庸或塌缩到自我强化的少数模式）。关键认知：

- **调高 temperature 不能解决多样性问题**。如果模型因对齐训练而"过度自信"，提高 temperature 也无法带来语义空间上有意义的多样性，只是增加表层措辞噪声。
- 根因是对齐训练带来的 **typicality bias（典型性偏好）**：当多个回答效用相当时，模型把"最典型/最 stereotypical"的答案当作 tiebreaker，从而塌缩到少数模式。RLHF 把模型困在一个"安全吸引盆地"里。
- **检索增强（RAG）是双刃剑**：相似度检索会把想法**偏向"已被充分表达的聚类"**，强化保守、增量式思考，反而压制新颖度。知识图谱式检索更能暴露跨域路径。

### 提升多样性/新颖度的方法工具箱

| 方法 | 机制 | 报告效果/出处 |
|---|---|---|
| **Verbalized Sampling (VS)** | 不要单条，而是 prompt 模型"给出 5 条候选及各自概率"，逼模型逼近预训练分布而非塌缩到典型模式 | 创意写作多样性提升 1.6–2.1×，恢复约 66.8% base model 多样性（2510.01171） |
| **Nova 迭代规划+检索** | 有计划地分轮检索外部知识，渐进式拓宽视野，再生成 | 独特新颖想法 **3.4×**，top-rated 想法 **≥2.5×**（170 篇 seed paper，Swiss Tournament 评估，2410.14255） |
| **Persona/角色多样性 + 多智能体** | 实例化不同 persona 的 agent 联合 brainstorm，扩张解空间；debate 式批判催生跨学科创意 | Persona 多智能体协作（2512.04488）、Diversity of Thought（2310.07088） |
| **Divergent-Convergent（CreativeDC）** | 把"无约束发散 ideation"与"约束满足收敛"两阶段解耦，对应 Guilford 发散/收敛认知 | 2512.23601 |
| **进化/树搜索（FunSearch / AI Scientist v2 / EvoScientist）** | LLM 作为变异算子 + 多岛种群选择；想法树搜索 + 锦标赛选择 + 失败记忆蒸馏 | EvoScientist 用 ideation memory 蒸馏失败，新颖/可行性双升 |
| **知识图谱检索** | 关系检索暴露跨域路径，避免最近邻塌缩到热门聚类 | 创意综述（2511.07448） |
| **结构化"质疑前提"prompt** | Bit-Flip-Spark 等系统性挑战默认假设 | 2511.07448 |

## 三、新颖度/多样性如何"可量化"

要让"靠谱"和"不重复"可度量，学界把指标分为三类（综述 2511.07448、NoveltyBench 2504.05228、OpenReview mnB4hDTIDr）：

**多样性（一组想法的广度）**
- **N-gram 类**：Distinct-N（唯一 n-gram / 总 n-gram，越高越不重复）、Self-BLEU（越低越多样）。
- **语义类**：对每条 idea 取 embedding，两两 **cosine 相似度**衡量塌缩程度。
- **Non-Duplicate Ratio（去重存活率）**：经过 embedding 去重过滤后还"活下来"的想法占比——**这正是"今天 20 条里有几条真不重复"的直接量化**。

**新颖度（单条 idea 与已有知识的距离）**——综述提出三种互补视角：
- **ON（绝对语义距离）**：与历史 idea 库 / 已有产品库的 embedding 距离。
- **RND（相对局部密度）**：在已有想法密集区 = 拥挤 = 不新；稀疏区 = 新。
- **SciND（符号/概念可解释）**：基于概念实体的可解释新颖度。

**质量/效用**：novelty、excitement、feasibility、effectiveness 四维（Stanford 用法），用 **LLM-as-Judge** 做可扩展打分，但需警惕 reward hacking，并配合少量人评校准。

一个关键工程原则：**novelty 与 diversity 是两件事**——novelty 衡量单条离已知多远，diversity 衡量整组覆盖多少个方向。每日产出要同时优化两者，否则会出现"20 条都很新但都在同一方向"或"很分散但都很平庸"。

## 四、对 idea-factory / idea-evl 的具体借鉴与可落地建议

**给 idea-factory（生成侧，保持离线 demo 契约的前提下也能先用规则/embedding 实现骨架）：**

1. **把"一次性生成"改造成"发散→去重→收敛"两阶段流水线**，新增 stage：`generate`（发散，过量产出，如先出 40~60 条候选）→ `dedup`（embedding 去重）→ `ranks`（收敛筛选到 10~20 条）。这与现有 normalize→generate→rank→export 结构天然契合，只需在 generate 与 rank 之间插入去重 stage。
2. **采用 Verbalized Sampling 风格的 prompt**：未来接 LLM 时，让模型一次"给出 N 条候选 + 各自的新颖度/置信度估计"，而不是逐条生成；这是成本最低、收益最高的抗 mode-collapse 手段。
3. **三源各配不同 persona/检索策略**：外部事件源（用 collect.py 的 HN/PH/RSS 信号做 RAG 种子）、用户脑海 idea（用户输入做 seed）、痛点模拟（不同目标人群 persona 的 agent）。三源用**不同的 persona 与不同的检索上下文**，从源头保证多样性，避免三条管道塌缩到同一聚类。
4. **引入"已产出 idea 库"作为新颖度护栏**：每天生成时，把候选与历史 idea 库（data/processed/ 累积）做 embedding 距离比较，**离已有库太近的直接丢弃**——这就是离线可实现的 Non-Duplicate Ratio 闸门，保证"每天不重复"。
5. **配额式多样性（diversity quota）**：要求每日 10~20 条覆盖 N 个不同主题/人群 bucket（类似 Nova 的 Swiss Tournament 思路），避免单方向霸屏。

**给 idea-evl（评估侧）：**

6. **不要只评 ideation 分，要补"执行/落地折扣"**。Ideation-Execution Gap 表明高新颖分会虚高。建议 idea-evl 输出**至少两组分**：ideation 分（novelty/excitement）与 **feasibility/可执行性分**，并对新颖度高但可行性低的 idea 施加显式惩罚或单独标注。
7. **四维 + 双层评分采用 ResearchAgent 式 ReviewingAgent**：用多个评审 agent（标准从真实人类偏好提炼），对 novelty、feasibility、market-fit、effort 分别打分，迭代给生成侧反馈，形成 generate↔review 闭环。
8. **量化指标内建为可回归的数字**，而非纯文字理由：每条 idea 落地 distinct-N 贡献、与库的 ON 距离、LLM-as-Judge 四维分；这些数字让"靠谱"可排序、可监控、可做日报趋势。
9. **用人评做小样本校准**：定期抽样人评，校正 LLM-as-Judge 的漂移与 reward hacking（综述明确警告 LLM-judge 易被 hack）。

**整体架构建议**：idea-factory 负责"过量发散 + 去重 + 初筛"，idea-evl 负责"多 agent 评审 + ideation/feasibility 双层打分 + 反馈"，两者通过共享 idea 库（带 embedding 与历史分）解耦协作。这与现有仓库的 stage 化设计、collect.py/match.py 既有能力可平滑衔接，且在接入真实 LLM 前可先用 embedding + 规则实现骨架，符合离线 demo 的非目标约束。

## 参考链接

- The AI Scientist (Sakana, blog): https://sakana.ai/ai-scientist/
- AI Scientist-v2 (GitHub): https://github.com/sakanaai/ai-scientist-v2
- Evaluating Sakana's AI Scientist (arXiv 2502.14297): https://arxiv.org/abs/2502.14297
- Can LLMs Generate Novel Research Ideas? (Stanford, arXiv 2409.04109): https://arxiv.org/abs/2409.04109
- 同上 OpenReview: https://openreview.net/forum?id=M23dTGWCZy
- The Ideation-Execution Gap (arXiv 2506.20803): https://arxiv.org/abs/2506.20803
- ResearchAgent (NAACL 2025 / arXiv 2404.07738): https://arxiv.org/abs/2404.07738
- Nova: Iterative Planning and Search for Novelty/Diversity (arXiv 2410.14255): https://arxiv.org/abs/2410.14255
- Verbalized Sampling: Mitigate Mode Collapse, Unlock Diversity (arXiv 2510.01171): https://arxiv.org/html/2510.01171v1
- LLMs for Scientific Idea Generation: A Creativity-Centered Survey (arXiv 2511.07448): https://arxiv.org/html/2511.07448v1
- Escaping Mode Collapse via Geometric Regulation (ICML 2026, arXiv 2605.00435): https://arxiv.org/html/2605.00435
- NoveltyBench: Evaluating Creativity and Diversity (arXiv 2504.05228): https://arxiv.org/html/2504.05228v1
- Evaluating Diversity of LLM-Generated Outputs (OpenReview): https://openreview.net/pdf?id=mnB4hDTIDr
- Divergent-Convergent Thinking / CreativeDC (arXiv 2512.23601): https://arxiv.org/pdf/2512.23601
- Persona-based Multi-Agent Collaboration for Brainstorming (arXiv 2512.04488): https://arxiv.org/pdf/2512.04488
- Diversity of Thought Improves Reasoning (arXiv 2310.07088): https://arxiv.org/pdf/2310.07088
- FunSearch (LLM-guided evolutionary search, overview): https://www.emergentmind.com/topics/funsearch-algorithm
- EvoScientist: Multi-Agent Evolving AI Scientists (arXiv 2603.08127): https://arxiv.org/pdf/2603.08127
