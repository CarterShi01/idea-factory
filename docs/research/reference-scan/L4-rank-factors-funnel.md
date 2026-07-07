---
doc: research
lane: L4
title: "rank:排序、因子库与多级漏斗"
date: 2026-07-07
agent: subagent
---

# L4 rank:排序、因子库与多级漏斗

## 结论速览

Top 3:**twitter-the-algorithm**(生产级多级漏斗 + 打散/个性化 boost 的最完整公开先例,AGPL 只能借概念)、**microsoft-qlib**(MIT,因子=声明式表达式 + 单一算子真相源的因子库工程范式)、**fast-map-dpp**(Apache-2.0,单文件贪心 MAP DPP,可抄成 stdlib 纯函数补足 MMR)。

最重要的发现:**我们的 rank 段设计在 Twitter 开源的生产系统里几乎逐件有同构先例**——alpha 加权和 ≙ heavy ranker 的 engagement 加权融合(含负权重惩罚,Report=-369);`_COMMODITY_DIST_PENALTY` 乘性硬罚 ≙ `OONTweetScalingScorer`/`VerifiedAuthorScalingScorer` 的乘性 scaling scorer;`per_edge_cap` 硬配额 ≙ `DiversityDiscountProvider` 的位置衰减打散公式 `score * ((1-0.25) * 0.5^position + 0.25)`(乘性衰减带地板,比硬 cap 更平滑,值得提案)。founder_fit 个性化 boost 的先例就是这类"base score × 一叠小的乘性 scorer 组件"模式。

## 推荐候选(Top 2–3,按价值排序)

### twitter-the-algorithm
- repository: github.com/twitter/the-algorithm(姊妹仓 github.com/twitter/the-algorithm-ml)
- stars: ~73.5k · license: **AGPL-3.0(两仓均是——绝不可抄代码,只能借概念)** · 活跃度: 2023-03 一次性开源后基本冻结,无后续维护——但它是"历史快照"型参考,冻结不减价值
- mined_for:
  - 数据面: 无(AGPL,且其权重/特征是 Twitter 业务专属)
  - 机制面: ①多级漏斗配比先例(5 亿→1500 candidates→light ranker(LR)→heavy ranker(NN)→heuristics,每级模型成本递增、量递减——与我们"LLM 成本梯度"同一原则的非 LLM 版);②加权多目标融合含**负权重**(Negative feedback=-74、Report=-369——我们 alpha 目前只有乘性罚,可提案给 anti-fit/speculative 信号负权重路径);③作者打散的**乘性位置衰减**公式(`(1-floor) * decay^position + floor`,比 per_edge_cap 硬砍更平滑、保留桶内顺位信息);④"base score × 乘性 scaling scorer 组件栈"模式——每个 scorer 是独立小组件(OON scaling、verified-author boost),即 founder_fit 类个性化 boost 的生产级同构先例
- 挖什么: `home-mixer/server/src/main/scala/com/twitter/home_mixer/functional_component/scorer/DiversityDiscountProvider.scala`(打散衰减公式)、同目录 `OONTweetScalingScorer.scala` / `VerifiedAuthorScalingScorer.scala`(乘性 boost 组件模式)、the-algorithm-ml `projects/home/recap/README.md`(heavy ranker 权重表与融合公式,README 本身就是完整规格,无需读代码);辅助入口:github.com/igorbrigadir/awesome-twitter-algo(社区注解版,定位文件最快)
- SKIP 什么: 整个 candidate-generation 半场(GraphJet/SimClusters/TwHIN/Earlybird——图嵌入基建,与我们无关);所有 Scala/Bazel 工程本体;the-algorithm-ml 的模型训练代码(masknet 等)
- 坑: 一次性开源、与 X 线上现状早已脱节(权重表标注 2023-04);仓库巨大,直接浏览易迷路,先走 awesome-twitter-algo 注解;两仓 AGPL,连"改写得很像"都要避免——**读 README/公式,重新表述后自己实现**
- recommendation: concepts-borrow
- 理由: 我们 rank 段每个机制(加权融合/乘性罚/配额打散/个性化 boost)唯一成体系的生产级公开先例,概念含金量全 lane 最高
- 与硬约束的冲突: AGPL-3.0 → 强制 concepts-borrow,禁止抄代码;裁剪方式=只挖公式与组件划分模式,stdlib 手写。成本梯度无冲突(它本身就是成本梯度的教科书)

### microsoft-qlib
- repository: github.com/microsoft/qlib
- stars: ~45.8k · license: MIT · 活跃度: 中——最近 release v0.9.7(2025-08),MSRA 维护重心已偏向 RD-Agent 自动化,但 issue 仍有响应,非停更
- mined_for:
  - 数据面: 无(Alpha158 因子是 OHLCV 时间序列表达式,领域不同不能直接 promote;但其"因子清单=配置文件"的**格式**可作我们 factors 词表/权重外置化的模板)
  - 机制面: ①**因子=声明式表达式、算子=单一真相源**的因子库工程范式——158 个因子全部是 `ops.py` 里少量纯算子的组合表达式(如 `Ref($close,60)/$close`),因子定义与计算引擎彻底分离,天然防漂移(正是 freqtrade 教训的正面解法,我们 factors/__init__.py 的下一步演进方向:词表+组合规则进 config,纯算子留代码);②因子按语义族命名分组(KBAR/ROC/STD/CORR…)+ 统一 handler 出 `dict[name, float]`,与我们 `compute_factors` 契约同构,可借其命名/版本化约定
- 挖什么: `qlib/data/ops.py`(算子库——看它如何把全部因子收敛到 ~40 个纯算子)、`qlib/contrib/data/loader.py` 的 Alpha158 `get_feature_config`(因子=配置清单的组织方式)、`qlib/contrib/data/handler.py` 的 `parse_config_to_fields`(配置→因子函数的翻译层)
- SKIP 什么: 整个数据平台/回测/RL/模型 zoo(重型运行时,与"只挖不跑"无关);RD-Agent 联动(LLM 自动因子挖掘,方向有趣但属 L8/未来,且诱导"LLM 产因子表达式"需人审)
- 坑: 文档与代码有版本漂移(issue #1564 实证 Alpha158 与引擎耦合较深,"只借表达式清单"比"借 handler 机制"容易);依赖极重,绝不可引
- recommendation: concepts-borrow
- 理由: "因子库怎么工程化才不漂移"这个问题的最权威开源答案,MIT 下连纯算子实现都可参照抄写
- 与硬约束的冲突: 依赖重(pandas/numpy/…)→ 只挖不跑、绝不引依赖;表达式引擎若照搬会超出当前需要(我们因子仅 8 个),裁剪方式=只借"定义外置、算子收敛"的分离原则,不引表达式解析器

### fast-map-dpp
- repository: github.com/laming-chen/fast-map-dpp
- stars: ~130 · license: Apache-2.0 · 活跃度: 单作者、仅 5 commits、多年不更——但它是 NeurIPS 2018 论文(Hulu, Chen et al. 1709.05135)的参考实现,算法冻结即完成,停更不构成风险
- mined_for:
  - 数据面: 无
  - 机制面: 贪心 MAP DPP 选择(O(M³)、增量 Cholesky)——比 MMR 更原理化的"质量×多样性"子集选择:MMR 只罚与已选项的**最大**相似度,DPP 罚的是整个已选集的**体积重叠**,对"4 条『语音备忘转任务』占领头部"这类聚簇更稳。可作 `select.py` 里 MMR+硬 Jaccard 去聚类的第三选项(或替代品),同一个 token-Jaccard 相似度矩阵直接复用
- 挖什么: `dpp.py`(全部价值所在,~60 行 numpy:核矩阵构造 `L = diag(q)·S·diag(q)` + 贪心增量选择循环)——翻译成 stdlib list-of-list 版本即可,k≤50 的规模下 O(M³) 毫无压力
- SKIP 什么: 无可 skip 的部分(仓库只有一个算法文件 + 测试)
- 坑: numpy 向量化写法翻 stdlib 时注意数值稳定项(对角线加 epsilon);质量分 q 与相似度 S 的相对尺度需要调(论文用 exp(θ·q) 调节质量-多样性权衡,等价于我们的 diversity_lambda)
- recommendation: adopt(Apache-2.0,抄一个纯函数并改写为 stdlib——符合 glue-only 的第二优先级)
- 理由: 用一个可直接移植的纯函数,把我们"MMR 软罚 + Jaccard 硬砍"两段补丁升级为有理论根的单一选择器,零依赖零 token
- 与硬约束的冲突: 实现依赖 numpy → 裁剪方式=手工移植为 stdlib 纯函数(k≤50 规模可行);其余无

## 评估过但不推荐(skip 清单,防重爬)

- gorse(github.com/gorse-io/gorse)— skip:Apache-2.0 且活跃(v0.5.10, 2026-06),但架构绑定 MySQL/Redis/分布式节点,多路召回合并逻辑平淡无可抄的纯函数;且新主打方向是 **LLM reranker(让 LLM 做排序)——与成本梯度第一原则正面冲突**,登记它反而是诱导源
- recommenders-team-recommenders(github.com/recommenders-team/recommenders)— skip:MIT、21.8k stars、Linux Foundation 背书,但 notebook 教学库+依赖极重,rank 段可挖的只有 evaluation 里几个 diversity/novelty 指标函数,价值密度低;其多样性**指标**对 L8 retro 或有残值(交叉 lane 备注)
- freqtrade(github.com/freqtrade/freqtrade)— skip:**GPL-3.0**(不能抄代码);其"策略-回测同源防漂移"教训已内化进本仓 factors 设计(CLAUDE.md 明文),无新增可挖
- the-algorithm-ml(github.com/twitter/the-algorithm-ml)— 不单列:AGPL,其唯一高价值资产(heavy ranker 权重表 README)已并入 twitter-the-algorithm 条目
- DPP-MAP-Inference(github.com/Alnusjaponica/DPP-MAP-Inference)— skip:lazy-greedy 学术复现,常数优化对 k≤50 无意义,fast-map-dpp 已够
- k-DPP-reco-engine(github.com/mayankmanj/k-DPP-reco-engine)— skip:单作者练手仓,无权威背书,DPP 核学习超出我们需要
- KunQuant(github.com/Menooker/KunQuant)— skip:因子表达式**编译器**(C++/SIMD),解决的是我们不存在的性能问题
- QuantaAlpha(github.com/QuantaAlpha/QuantaAlpha)— skip:LLM 进化式自动挖因子,方向属未来 retro/校准议题且诱导"贵模型产因子"成本梯度风险,现阶段不登记
- alphalens / alphalens-reloaded(github.com/stefan-jansen/alphalens-reloaded)— skip:因子 IC/分位数分析属**事后校准**,归 L8 retro lane 评估更合适(交叉 lane 备注:预测因子 vs 实际 outcome 的 IC 分析概念可借)
- apricot(github.com/jmschrei/apricot)— skip:子模优化选择库,MIT 且质量高,但组合级子集选择归 L7 portfolio lane,rank 段的 DPP 需求 fast-map-dpp 已覆盖
- datawhalechina/fun-rec — skip:中文推荐系统教程仓,漏斗概念讲义齐全但无生产级可抄资产,不如直接读 Twitter 真系统

## 本 lane 的搜索方法沉淀

- **最有效入口**:①`twitter the-algorithm heavy ranker light ranker diversity heuristics`——直接命中生产级漏斗全套;再经 **igorbrigadir/awesome-twitter-algo**(社区注解版)定位到具体 Scala 文件(DiversityDiscountProvider 等),比在 73k-star 大仓里裸逛快一个数量级。"大厂开源快照 + 社区 awesome 注解仓"是挖生产系统的标准双跳路径。②论文→官方实现:搜 `fast-map-dpp`(arXiv 1709.05135)直达 Apache-2.0 单文件实现——**"NeurIPS/KDD 工业论文 + 第一作者 GitHub"** 这条路挖到的算法仓通常小而纯,最适合 stdlib 移植。
- **有效但需过滤**:`qlib alpha158 expression engine` 能命中因子工程范式,但 qlib 文档漂移,要落到具体文件(ops.py/loader.py)而不是 readthedocs。
- **死胡同**:①泛搜 "recommender system open source"——命中的全是要跑起来才有价值的服务型框架(gorse/merlin/monolith),对"只挖不跑"几乎无产出;②搜 "MMR implementation github"——碎片化 gist 和 langchain 内嵌版,质量不如我们已有实现,无需再挖;③"personalized boost ranking" 类检索词命中的是 Elasticsearch function_score 文档(Elastic license 灰区且是 DSL 不是算法),founder_fit 先例最终在 Twitter 的 scaling scorer 组件里找到——**个性化 boost 要搜 "scorer component / score scaling" 而不是 "personalization"**。
