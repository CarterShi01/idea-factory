# Idea 评估与打分方法论调研

> 服务目标：把经典创业评估框架（YC / Paul Graham / Sequoia / TAM-SAM-SOM / Founder-Market Fit / Mom Test / RICE-ICE / 风险清单）系统化，落地为 **idea-evl** 可直接实现的「多维评分表 + LLM-as-judge + 对抗式批判」评估引擎。idea-factory 每天产出 10~20 条候选 idea，idea-evl 负责给它们打分、排序、筛掉伪靠谱项。

---

## 一、经典评估框架盘点（先有"对"的判断标准，再谈 LLM 怎么打分）

### 1. Paul Graham / YC：好 idea 的本质特征

PG 在《How to Get Startup Ideas》里给出的核心，是判断 idea 是否"有机生长"出来的，而不是"硬想"出来的。最值得固化成 rubric 的几条：

- **三要素**：最好的 idea 同时满足——(a) 创始人自己就想要、(b) 创始人自己能做出来、(c) 很少有人意识到这件事值得做。
- **井 vs 泥潭（Well vs Tarpit）**：好 idea 是"少数人极度需要"（井，深而窄，如 Facebook 从哈佛起步）；坏 idea 是"很多人觉得还行但没人真的用"（泥潭，宽而浅，如"给宠物主人的社交网络"）。
- **关键测试句**："谁会如此需要它，以至于哪怕只是一个粗糙的 v1 也愿意用？"（Who wants this so much they'll use a crappy version one?）
- **自用测试**："如果不是你写的，你自己会用它吗？"
- **Schlep blindness（怕做苦活的盲区）**：对枯燥、痛苦实现路径的恐惧，会让人无意识地过滤掉好 idea（Stripe 啃下了支付这块硬骨头）。
- **假阳性过滤器（要警惕的 bad reasons to reject）**：① unsexy（不性感就否掉）；② 市场已拥挤（把竞争当作否决项，而非需求被验证的信号）；③ 看起来难启动。
- **创始人 > idea**：决心（determination）是最重要的特质，智力过线即可。

> 对 idea-evl 的启示：这些既是"加分项"也是"反向陷阱检测项"。LLM 评估时必须显式检查"这是井还是泥潭""这是不是被 unsexy/拥挤 错杀的好 idea"。

### 2. Sequoia Pitch 框架：一个完整 idea 应该回答的问题清单

Sequoia 经典模板的 10~12 个板块，本质是"一个 idea 必须能自洽回答的问题列表"，非常适合拆成评分维度：

| 板块 | 转成评估问题 |
|---|---|
| Company Purpose | 一句话能说清它存在的意义吗？ |
| Problem | 客户当下的痛点是什么、现在怎么凑合解决？ |
| Solution | 价值主张是否让客户的生活明显变好？ |
| **Why Now** | 为什么是现在？品类的历史演进 + 哪些新趋势让它成为可能？ |
| Market Size | TAM/SAM/SOM 是否可信？ |
| Competition | 谁在做、你的不公平优势是什么？ |
| Business Model | 怎么赚钱？ |
| Team | 创始人与这个市场匹配吗？ |

**"Why Now"** 是最容易被一人公司创业者忽略、却对 idea 质量极具区分度的维度——大多数 idea 以前有人试过且失败了，"为什么现在能成"必须有明确的技术/行为/监管变化作为支撑。

### 3. 市场规模：TAM / SAM / SOM 的可信度而非数字大小

- **TAM**（总可服务市场，自上而下）/ **SAM**（可服务可获得市场，自下而上 = ICP 数量 × ACV）/ **SOM**（可获得市场，从销售产能反推）。
- 投资人核心是看**逻辑而非数字**：一个"2万亿全球市场、无任何过滤条件"的 TAM 反而立刻失去可信度。
- 黄金法则：自上而下与自下而上两种算法结果应落在同一量级；SOM 必须与财务预测互相印证。

> 对 idea-evl：市场维度不该奖励"市场大"，而该奖励"市场估算逻辑自洽、自上/自下一致、有明确边界条件"。这是 LLM 容易拍脑袋编大数字的地方，必须强约束。

### 4. Founder-Market Fit（创始人-市场匹配）

Chris Dixon：founder/market fit 是预测能否达成 product/market fit 的最佳指标——创始人对所进入市场有深刻理解，"人即产品/即公司"。对一人公司场景尤其关键：idea-evl 应该结合**用户自身的技能画像/兴趣画像**来打这一分，而不是抽象评估。

### 5. The Mom Test：验证可行性，而非验证赞美

Rob Fitzpatrick 的三条规则——① 聊对方的生活，别聊你的 idea；② 问过去的具体事实，别问未来的假设；③ 多听少说。核心洞察：只要你不提自己的 idea，就会自动问出更好的问题。

> 对 idea-evl：可生成"针对该 idea 的 Mom-Test 合规验证问题清单"，并对 idea 自带的"需求证据"做打分——是**具体的过去行为证据**，还是**假设性的恭维**？这是过滤伪需求的利器。

### 6. RICE / ICE：可量化的优先级打分

- **RICE = (Reach × Impact × Confidence) / Effort**（源自 Intercom）。
- **ICE = Impact × Confidence × Ease**，少了 Reach、用 Ease 替代 Effort，计算更轻，适合每天批量打 10~20 条 idea。
- **Confidence 是关键的风险调节因子**：它把"我对 Reach/Impact 估计有多确信"显式建模——这恰好和"LLM 打分需要输出置信度"天然契合。

### 7. 风险清单：idea 会从哪里崩

42% 的创业失败源于"没有市场需求"。常用六大风险面：**市场、产品、团队、财务、运营、合规**。再叠加专门的：

- **市场风险**：问题够大够急吗？
- **执行风险**：能招到/自己能搭出团队与产品吗？
- **技术风险**：会不会撞上技术墙？
- **时机风险（Why Now）**：为什么是现在？
- **资金/现金流风险**：一人公司尤其要看"低成本能否撑到验证"。

---

## 二、把框架转成 LLM 可执行的评估引擎

LLM-as-judge 的可靠性"只取决于喂给它的 rubric"——维度模糊 → 评分不稳；维度缺失 → 盲区；评分刻度没校准 → 分布压缩、好坏不分。落地要点（来自学术综述与工程实践）：

**核心设计原则**
1. **维度分解优于单一总分**：跨多个明确维度分别打分，比一个聚合分更稳健、更可诊断（能定位是哪一维在拉胯）。
2. **每个维度要有"分档描述 + 锚点样例"**：不要只写"市场1-5分"，要写清每一档长什么样，并附 worked example。
3. **先推理后打分（CoT）**：要求 LLM 先写"判断依据/证据/逻辑顺序"，再给分。证据要具体（引用、数值核对、逻辑链），而非空泛形容词。
4. **用少量人工标注校准**：拿 10~30 条人工打过分的 idea 做基准，迭代 rubric 直到 LLM 与人工一致性达标（如 Krippendorff's α ≈ 0.8）。

**已知偏差与对策**（idea-evl 必须内建防御）

| 偏差 | 表现 | 对策 |
|---|---|---|
| Verbosity/啰嗦偏差 | 偏好更长的论证 | 长度归一化、提示"长≠好" |
| Position 偏差 | 偏好特定位置选项 | 随机化顺序、对称格式 |
| Self-enhancement | 偏爱自家模型输出（idea 若由同一 LLM 生成，评估会偏高）| 生成与评估用不同模型/不同 prompt；多评委 |
| Overconfidence | 置信度失真 | 多次采样看判断分布 |
| Sycophancy | 轻信未经核实的说法 | rubric 要求"区分证据 vs 假设" |

**对抗式批判 / 多评委**：让两个 LLM 就同一 idea 辩论（一个 steelman 看多、一个 red-team 看空），或用"评委小组"分别打分再聚合，可显著降低单模型自我增强偏差；多次采样的"判断分布"还能暴露哪些 idea 评分模糊、需要人工复核。

---

## 三、给 idea-evl 的可落地设计（可直接实现）

### A. 多维评分表（建议 7 维，每维 1~5 分 + 证据 + 置信度）

| 维度 | 定义（问题） | 1 分锚点 | 5 分锚点 | 理论出处 |
|---|---|---|---|---|
| Problem Severity | 痛点有多急多痛？ | 可有可无的小烦恼 | 客户现在用痛苦的土办法硬扛 | Mom Test / 风险 |
| Demand Depth（井 vs 泥潭）| 是否有人极度需要 v1？ | 很多人"还行"没人真用（泥潭）| 少数人迫切要（井）| PG |
| Why Now | 为什么是现在能成？ | 没有任何新变化 | 有明确技术/行为/监管拐点 | Sequoia |
| Market Logic | TAM/SAM/SOM 逻辑自洽？ | 拍脑袋大数字无边界 | 自上/自下一致、边界清晰 | TAM-SAM-SOM |
| Founder-Market Fit | 与用户技能/兴趣匹配？ | 完全陌生领域 | 用户即该领域深度从业者 | Dixon |
| Feasibility/Schlep | 一人公司能否低成本做出 v1？ | 需要大团队/重资本 | 周级可做 MVP，苦活是护城河 | PG schlep / RICE-Effort |
| Moat/Competition | 有无不公平优势？ | 纯红海无差异 | 拥挤但你有独特切入（拥挤=需求验证）| PG / Sequoia |

**聚合公式**（借鉴 RICE 的"价值/成本，置信度调节"）：

```
RawValue = (ProblemSeverity × DemandDepth × WhyNow × MarketLogic × FounderFit × Moat)
Score    = RawValue × meanConfidence / Feasibility(Effort)
```

每个分项输出 `{score, confidence(0~1), evidence}` 三元组；置信度低于阈值的 idea 进"人工复核"队列而非直接淘汰。

### B. LLM-as-judge 实现要点（结合现有 collect.py/match.py 数据）

1. **结构化输出**：强制 JSON schema —— 每维 `{dimension, score, confidence, rationale, evidence_quotes}`，便于复用现有 export.py 的 JSON/Markdown 双输出。
2. **先推理后打分**：prompt 内先要求逐维写 rationale，再给分；rationale 必须引用 idea 文本或 collect 到的外部信号作为证据。
3. **防自我增强**：idea 由 generate.py（LLM）产出时，评估务必换模型或换 system prompt，避免"自夸"。
4. **Mom-Test 证据检测器**：单独一个子 judge，判断 idea 的"需求证据"是过去行为证据还是假设，输出布尔 + 置信度。

### C. 对抗式批判（red-team pass，建议作为独立 pipeline 阶段）

每条进入决赛圈的 idea 跑一轮三角色：

- **Bull（看多/steelman）**：给出最强支持论证。
- **Bear（看空/red-team）**：用风险清单（市场/执行/技术/时机/资金）逐项找致命假设——"它会从哪里崩？"
- **Judge（裁决）**：对照 Bull/Bear，输出最终分 + 置信度 + "kill reason or proceed"。

可选**辩论模式**：Bull/Bear 两轮往返后再裁决，研究表明辩论能逼模型重审初判、得到更真实的结论。

### D. 与现有仓库的衔接（具体落点）

- 在 idea-evl 新建 `evaluate.py`（多维评分）+ `critique.py`（对抗批判）两个模块，保持单一职责，呼应 idea-factory 的 normalize/generate/ranks 分层风格。
- 评估的输入直接吃 idea-factory 的候选 idea JSON；输出复用同款 JSON+Markdown，便于人审。
- **离线契约**：rubric/prompt 本身不需联网；调 LLM API 属于"显式开启"的能力，应像 idea-factory 的 collect.py 一样做成 opt-in，离线 demo 路径可用 mock judge（固定权重 ICE 打分）兜底，保持端到端可跑。
- 把人工标注样本（10~30 条）存为 `data/raw/eval_calibration.json`（合成/脱敏数据），作为 rubric 回归校准基准。

### E. 每日 10~20 条的工作流建议

1. ICE 轻量初筛（便宜、批量）→ 砍掉明显泥潭。
2. 7 维 LLM-as-judge 精评（带置信度）→ 排序。
3. Top-N 跑对抗式批判（Bull/Bear/Judge）→ 出最终"靠谱清单"+ 每条的 kill-risk 说明。
4. 低置信度的进人工复核队列。这样既稳定产出，又不让 LLM 的过度自信淹没真正的好 idea。

---

## 参考链接

- Paul Graham 原文《How to Get Startup Ideas》：http://www.paulgraham.com/startupideas.html
- YC Startup Library 同篇：https://www.ycombinator.com/library/8g-how-to-get-startup-ideas
- Sequoia Pitch Deck 模板与板块解析：https://pitchbuilder.io/blogs/news/what-is-the-sequoia-pitch-deck-model
- Sequoia 推荐格式（含 TAM/SAM/SOM）：https://www.slidegenius.com/cm-faq-question/what-is-the-recommended-format-for-a-pitch-deck-according-to-sequoia
- 投资人如何用 TAM/SAM/SOM 评估：https://www.goingvc.com/post/how-investors-use-tam-sam-som-to-evaluate-startups
- 市场规模幻灯片（自上/自下一致性）：https://qubit.capital/blog/market-size-slide-pitch-deck
- Chris Dixon《Founder/market fit》：https://cdixon.org/2011/06/19/foundermarket-fit/
- a16z《12 Things About Product-Market Fit》：https://a16z.com/12-things-about-product-market-fit/
- The Mom Test 三条规则：https://www.atlantaventures.com/blog/the-3-rules-to-customer-interviews-from-the-mom-test
- RICE 评分框架（Tempo）：https://www.tempo.io/guides/rice-score-prioritization-framework-product-management
- ICE / RICE / 加权评分对比：https://www.kaizenko.com/scoring-frameworks-ice-rice-and-weighted-scoring-for-product-prioritization/
- 创业风险类型（NFX）：https://www.nfx.com/post/founders-startup-risk-types
- 杀死创业的 10 大风险：https://www.colinkeeley.com/blog/the-10-risks-that-will-kill-your-startup
- 创业评估清单（Qubit Capital）：https://qubit.capital/blog/startup-evaluation-checklist
- LLM-as-a-Judge Rubric 设计（Appen）：https://www.appen.com/llm-as-a-judge-rubric-design
- LLM-as-a-Judge 完整指南（Evidently AI）：https://www.evidentlyai.com/llm-guide/llm-as-a-judge
- LLMs-as-Judges 综述（arXiv 2412.05579）：https://arxiv.org/pdf/2412.05579
- From Generation to Judgment 综述（arXiv 2411.16594）：https://arxiv.org/pdf/2411.16594
- 辩论提升答案真实性（arXiv 2402.06782）：https://arxiv.org/pdf/2402.06782
- Rubric-Based Evals & LLM-as-a-Judge（Medium）：https://medium.com/@adnanmasood/rubric-based-evals-llm-as-a-judge-methodologies-and-empirical-validation-in-domain-context-71936b989e80
