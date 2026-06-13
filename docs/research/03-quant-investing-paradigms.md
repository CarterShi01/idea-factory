# 从量化投资开源项目借鉴：把"选股"范式迁移到"选 idea"

> 调研范围：qlib / RD-Agent、backtrader、freqtrade、FinGPT(FinRL/FinNLP)、TradingAgents、StockAgent/FinMem、awesome-quant，以及 2025–2026 年涌现的 LLM 驱动 alpha 挖掘论文（AlphaAgent、QuantaAlpha、RD-Agent(Q)）。
> 核心结论：用户的直觉是对的。**"每天稳定产出 10~20 条靠谱 idea 并前期筛选"在结构上几乎等价于一条量化研究流水线**：信号(signal)→因子(factor)→打分(alpha)→回测(backtest)→组合(portfolio)→风控。下面把每个范式拆开，并明确映射到 idea-factory（负责因子化打分）和 idea-evl（负责回测/事后验证）。

---

## 一、量化研究的标准范式（被反复验证的那套）

把这几个项目对齐看，会发现它们共享同一条"骨架"，只是抽象层次不同：

| 阶段 | 量化里的含义 | 代表项目的体现 |
|---|---|---|
| **Signal（信号）** | 原始市场/新闻事件流，时效性强、信噪比低 | FinGPT 从 ≥34 个源实时采集，专门处理"高时效、强动态、低信噪比"三大难题 |
| **Factor（因子）** | 把原始信号变成可计算、可比较的特征 | qlib 的 Alpha158/Alpha360 因子集；backtrader 的 indicator |
| **Alpha（打分）** | 用因子预测未来收益，产出一个排序分 | qlib 的 Forecast Model 产出 alpha 信号；用 IC/RankIC 衡量预测力 |
| **Backtest（回测）** | 用历史数据验证"这个假设到底赚不赚钱" | freqtrade 的 Backtesting 类、backtrader 的事件驱动引擎 |
| **Portfolio（组合）** | 从一堆候选里选出 Top-N 并配权 | qlib 的 Portfolio Generator → Order Executor |
| **Risk（风控）** | 控制最大回撤、避免拥挤/过拟合 | 最大回撤 MDD、purged K-fold、因子拥挤(crowding)约束 |

**qlib 的四层架构最值得抄骨架**：DataServer（基础设施）→ Workflow（Information Extractor → Forecast Model → Portfolio Generator → Order Executor）→ Learning Framework → Interface。它用一个 `qrun` + YAML 把"建数据集→训练→回测→评估"全流程自动化（来源已核实）。这正是 idea-factory 当前 pipeline（normalize → generate → rank → export）想长成的样子，只是 qlib 多了**回测闭环**和**配置化编排**。

**freqtrade 有一条铁律值得照搬**：回测代码和实盘代码用同一个 `IStrategy` 接口，唯一区别是持久化层（回测用内存 `LocalTrade`，实盘用数据库 `Trade`）。映射到我们：**"评估 idea 的逻辑"和"生产 idea 的逻辑"应共用同一套因子定义**，否则回测出来的"靠谱"在生产时会失真。

---

## 二、四个对 idea 生产最关键的可迁移概念

### 1. 事件驱动（event-driven）
backtrader / Zipline / Nautilus 都按时间顺序逐条处理市场事件，从而能真实模拟滑点、延迟。对 idea-factory 的启示：**外部事件（HN/PH/RSS 抓到的新发布）应作为带时间戳的事件流逐条进入流水线**，而不是一次性批处理。这样 idea-evl 才能做"在事件发生当天，这条 idea 看起来如何"的 point-in-time 回测，避免 lookahead bias（用了当时还不存在的信息）。

### 2. 因子库（factor library）
qlib 的 Alpha158/Alpha360 把"造特征"标准化，研究者只管模型不用每次重造轮子。**idea-factory 应该建一个"idea 因子库"**：把判断一条 idea 是否靠谱的维度沉淀成可复用、可版本化的命名因子，例如 `market_freshness`（信号新鲜度）、`pain_intensity`（痛点强度）、`build_cost`（一人公司可实现性）、`moat_signal`（壁垒）、`competition_density`（红海拥挤度）、`distribution_fit`（与作者已有分发渠道的契合度）。每个因子是一个纯函数 `record -> float`，可单测、可回测。

### 3. 信号衰减 / 时效（signal decay / half-life）
这是本次调研最有价值的发现。2025–2026 年研究明确指出：在 AI 普及下，**中频因子的 alpha 半衰期已从过去的 5–7 年压缩到约 18 个月**；并区分了"机械型因子（动量/反转）会拥挤衰减"vs"判断型因子（价值/质量）不易拥挤"（arxiv 2605.23905 / 2512.11913，已核实）。
- 直接映射：**一条 idea 的"机会窗口"也会衰减**。某个外部事件刚发生时含金量最高，越多人看到越拥挤。idea-factory 应给每条 idea 打上 `freshness` 与 `decay_rate`，**对"人人都能想到"的机械型 idea 主动降权**，对"需要作者独特判断/独特数据"的 idea 加权。
- 落地：记录每条 idea 的"信号来源时间戳"，按指数衰减 `score *= exp(-λ·age)` 调整排序。

### 4. 回测验证假设（backtest hypothesis）
量化的核心信仰是：**任何赚钱主张都必须用历史数据证伪**。而 90%+ 的学术策略在实盘失效，主因是过拟合、lookahead bias、缺乏可解释性（已核实）。对 idea-evl 这是直接的方法论：评估 idea 不能只靠 LLM 当场打个分，而要做"事后验证"——把过去 3–6 个月产出的 idea 拉出来，对照"后来市场上是否真的出现了类似产品/是否有人验证了该痛点"，统计**命中率(hit ratio)**。

---

## 三、LLM 已经把"量化研究"和"idea 生产"显式打通了

最关键的一点：学术界已经把"LLM 自动挖因子"做成了和我们目标**结构同构**的系统，可直接抄循环。

- **AlphaAgent（arxiv 2502.16789，已逐字核实）** 用三个 agent 闭环：**Idea Agent**（CoT 生成市场假设）→ **Factor Agent**（把假设翻译成数学因子表达式，维护成功/失败知识库）→ **Eval Agent**（多维回测并把结果反馈给 Idea Agent 迭代）。这就是"脑海 idea → 结构化因子 → 评估 → 再生成"的完整回路。
  - 它对抗 alpha 衰减用了三个正则项，**每一个都能平移到 idea 评分**：
    1. **Originality（原创性）**：用 AST 子树同构检测与已有因子的相似度，惩罚雷同 → 对应 idea-evl 应**惩罚与历史已产出 idea 雷同的新 idea**（去重/反拥挤）。
    2. **Hypothesis Alignment（假设一致性）**：检查"假设—描述—表达式"语义是否自洽 → 对应**检查 idea 的"痛点—方案—目标人群"三者是否逻辑自洽**，过滤幻觉 idea。
    3. **Complexity Control（复杂度约束）**：限制符号长度防过拟合 → 对应**偏好可由一人公司落地的简单 idea**，惩罚"需要 50 人团队"的宏大叙事。
  - 它的质量指标体系（IC/RankIC 预测力、IR 风险调整、MDD 回撤、hit ratio 生成效率）可整套作为 idea-evl 的评分表骨架。
- **RD-Agent(Q)（微软 + HKUST，已核实）**：数据中心多智能体框架，把工作流拆成 **Specification → Synthesis(创意生成) → Implementation**，用"知识森林(knowledge forest)"持续精炼假设，**用 70% 更少的因子拿到 2× 收益**，且全部实验跑在 $10 以内。启示：**少而精 > 多而滥**——idea-factory 不该追求堆量，而是用反拥挤约束产出 10~20 条高密度 idea。
- **TradingAgents（arxiv 2412.20138，已核实）**：模拟一家交易公司，让基本面/情绪/技术分析师 + 风控团队**辩论**后决策。这正好对应用户三源头里的"模拟目标人群痛点分析"——可以用多 agent 扮演不同目标用户/不同投资视角对一条 idea 做对抗式审议。
- **FinMem / StockAgent**：引入**分层记忆 + 角色设定**。映射：idea-evl 应有"记忆层"记住作者偏好、历史决策与已否决的 idea，让评分随时间个性化。

---

## 四、对 idea-factory / idea-evl 的具体借鉴 / 可落地建议

### 给 idea-factory（负责"因子化打分"）

1. **建立 `factors.py` 因子库**（对标 qlib Alpha158）。每个因子是纯函数 `idea -> float`，集中注册、可单测。先落地 6 个：freshness、pain_intensity、build_cost、moat、competition_density、distribution_fit。当前 `ranks.py` 应从硬编码打分改为"加权因子求和"，权重写进配置。
2. **把打分配置化**（对标 qlib 的 YAML/`qrun`）。新增一个 `scoring.yaml` 声明因子权重与衰减系数 λ，让"换一套选 idea 哲学"不用改代码——保持离线契约，不引入网络调用。
3. **给每条 idea 带 point-in-time 时间戳**。`collect.py` 抓到的信号要保留 `observed_at`，`generate.py` 产出的 idea 继承它。这是 idea-evl 做无偏回测的前提。
4. **加入反拥挤/去重**（对标 AlphaAgent Originality）。新增 `dedup` 步骤：对新 idea 与历史 idea 做文本/embedding 相似度，过高则降权或合并。这能把"机械型人人能想到的 idea"自动压下去。
5. **三源头融合保持因子统一**：外部事件、脑海 idea、模拟痛点三类输入，归一化到**同一份 idea schema** 后走同一套因子打分（对标 freqtrade"回测=实盘同接口"），避免三套标准。

### 给 idea-evl（负责"回测 / 事后验证 idea 是否靠谱"）

1. **idea-evl 的本质是一个 backtester**。明确定位：输入一批带时间戳的历史 idea，输出"事后它们是否被市场验证"的命中率与校准曲线。这是和 idea-factory 的清晰边界——factory 产出+打分，evl 做闭环验证。
2. **采用 AlphaAgent 三 agent 回路**：Idea→Factor→Eval，且 **Eval 的反馈要回流去调 idea-factory 的因子权重**（在线学习）。这把两个仓库连成 RD-Agent 式的自进化循环。
3. **照搬量化质量指标表**：为 idea 评分定义 IC 类指标——"评分高的 idea 后续验证成功率是否真的更高"（即评分的 RankIC）；以及 hit ratio、calibration、"最大踩坑"(类比 MDD)。
4. **严防 idea 版的过拟合与 lookahead bias**：评估某条 idea 时只用其 `observed_at` 之前的信息；用 purged/walk-forward 思路切分历史 idea 训练评分权重，避免用"未来才知道的爆款信息"反推。
5. **多 agent 对抗审议**（对标 TradingAgents）：让"目标用户 agent / 竞品 agent / 一人公司可行性 agent / 投资回报 agent"辩论后给联合评分，比单次 LLM 打分更稳健、更可解释。
6. **记忆层**（对标 FinMem）：记录作者历史"接受/否决"决策，使评分随时间贴合作者真实偏好，并避免重复推荐已否决方向。

### 一句话蓝图
> **idea-factory = 信号采集 + 因子库 + alpha 打分 + 反拥挤；idea-evl = 回测引擎 + 多 agent 风控审议 + 命中率反馈。** 两者用统一 idea schema 连接，Eval 的反馈回流调权，构成一条 RD-Agent 式自进化的"idea 量化研究流水线"，每日稳定输出经过前期筛选的 10~20 条高密度候选。

---

## 五、需要警惕的反面教训（量化踩过的坑）
- **回测漂亮≠真实有效**：90%+ 学术策略实盘失效。idea-evl 必须做样本外/walk-forward 验证，别被"LLM 当场夸 idea 很好"骗了。
- **拥挤即死**：越多人能想到的 idea 衰减越快。把"原创性/反拥挤"做成一等公民。
- **少而精**：RD-Agent 用 70% 更少因子拿 2× 收益。目标是 10~20 条高密度，而非每天几百条噪声。
- **保持离线契约**：以上全部可在 idea-factory 当前离线 demo 路径内实现（因子库、配置化、去重、时间戳都不需要新网络调用），网络仅限既有的 opt-in `collect`。

---

## 参考链接（均来自本次搜索并对关键来源做了 WebFetch 核实）

- Qlib（GitHub，已 fetch）: https://github.com/microsoft/qlib
- Qlib 架构（DeepWiki）: https://deepwiki.com/microsoft/qlib
- Qlib 论文（Microsoft Research）: https://www.microsoft.com/en-us/research/publication/qlib-an-ai-oriented-quantitative-investment-platform/
- RD-Agent（Microsoft Research 介绍）: https://www.microsoft.com/en-us/research/articles/rd-agent-an-open-source-solution-for-smarter-rd/
- R&D-Agent-Quant 论文: https://www.microsoft.com/en-us/research/publication/rd-agent-quant-a-multi-agent-framework-for-data-centric-factors-and-model-joint-optimization/
- RD-Agent 案例分析（2× 收益 / 70% 更少因子）: https://saulius.io/blog/automated-quant-research-ai-agents-rd-agent
- freqtrade 回测/优化（DeepWiki）: https://deepwiki.com/freqtrade/freqtrade/3-testing-and-optimization
- freqtrade Hyperopt: https://deepwiki.com/freqtrade/freqtrade/3.2-hyperopt-optimization
- freqtrade 官方回测文档: https://www.freqtrade.io/en/stable/backtesting/
- backtrader 事件驱动架构（Medium）: https://medium.com/@jpolec_72972/building-a-robust-backtesting-framework-event-driven-architecture-22aa77eedf34
- Event-Driven Backtesting（QuantStart）: https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/
- awesome-quant: https://github.com/wilsonfreitas/awesome-quant
- awesome-systematic-trading: https://github.com/paperswithbacktest/awesome-systematic-trading
- awesome-ai-in-finance: https://github.com/georgezouq/awesome-ai-in-finance
- FinGPT（AI4Finance）: https://github.com/AI4Finance-Foundation/FinGPT
- FinGPT 论文（实时数据管线，34+ 源）: https://arxiv.org/pdf/2307.10485
- TradingAgents 论文: https://arxiv.org/abs/2412.20138
- TradingAgents 代码: https://github.com/TauricResearch/TradingAgents
- FinMem-LLM-StockTrading（分层记忆）: https://github.com/pipiku915/FinMem-LLM-StockTrading
- StockAgent: https://github.com/MingyuJ666/Stockagent
- AlphaAgent 论文（LLM 驱动 alpha 挖掘 + 反衰减，已 fetch）: https://arxiv.org/html/2502.16789v2
- QuantaAlpha（LLM 驱动 alpha 挖掘进化框架）: https://arxiv.org/html/2602.07085v1
- AI-Driven Alpha Decay（拥挤与信号侵蚀）: https://arxiv.org/abs/2605.23905
- Not All Factors Crowd Equally（因子拥挤建模）: https://arxiv.org/html/2512.11913v1
- The Half-Life of Alpha（半衰期 18 个月）: https://quantitativepy.substack.com/p/the-half-life-of-alpha-why-your-ml
- 回测过拟合对比研究（ScienceDirect）: https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110
- Walk-Forward 验证框架: https://arxiv.org/html/2512.12924v1
