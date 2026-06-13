## 摘要

本报告聚焦"创业 idea / 趋势 / 选题"赛道的商业 SaaS 竞品，覆盖三类玩家：(1) 趋势信号类（Exploding Topics、TrendHunter）、(2) idea 生成 / 选题类（IdeaBrowser、FounderPal、Buildpad、各类 AI idea generator）、(3) 受众痛点挖掘 / 知识沉淀类（GummySearch、Glasp）。另外补充了与 idea-evl 直接对位的"idea 评估打分"工具梯队（WorthBuild、IdeaProof、Validator AI 等）。

核心结论先行：

- **赛道已拥挤但分裂**。没有一家把"外部事件 + 用户脑内 idea + 模拟人群痛点"三源合一，多数只做其中一源。
- **数据源依赖是最大单点风险**。GummySearch 这种头部 Reddit 工具于 2025 年 11 月因拿不到 Reddit 商业 API 授权而关停（Reddit 商用 API 约 $0.24 / 1000 次调用）。这对"自建采集"既是警示也是机会。
- **"生成 idea"已商品化，"验证需求"才稀缺**。2026 年的共识是：好点子遍地，靠谱的"已验证需求"极少；纯 AI 生成的 idea 普遍被批"千篇一律、TAM 数字编造"。这正是 idea-evl 的护城河位置。

---

## 一、竞品对照表

| 产品 | 卖给谁 | 定价（核心） | 核心数据源 | 产出形态 | 主要局限 / 差评 |
|---|---|---|---|---|---|
| **Exploding Topics** | 创业者 / 投资人 / 营销 | Entrepreneur $79/mo、Investor $199/mo（均年付） | Google Trends + TikTok/FB/Reddit/Spotify/Amazon 等 100 万+ 源，ML + 人工分析师 | 趋势词库（110 万+ 趋势）、增长曲线、Meta Trends | 强制年付、低档限 10 次趋势分析、利基覆盖浅、趋势预测时准时不准、导出受限、有"未告知即扣全年费"投诉 |
| **TrendHunter** | 大企业创新 / 品牌 | PRO $199/mo/座（年付）；定制报告另计 | 3 亿+ 人群行为、5.2 亿+ 创新条目，人工研究员 + AI | 50 类趋势报告、Dashboard、定制研究、Horizon 信号引擎、工作坊 | 偏 B2B 企业咨询、价格高、对一人公司过重、产出偏"宏观趋势"非可执行 idea |
| **IdeaBrowser** | 想创业的 solopreneur / "wantrepreneur" | Free（1 idea/天）；Starter $299/yr；Pro $999/yr；Empire（社群+教练，更高额度） | Reddit 线索 + 搜索数据，AI agents + 人工 | 每日 idea、800+ idea 库、Research Agent 报告、Chat Strategist、Idea Builder | 本质是 Greg Isenberg 的高转化 lead magnet；Pro 仅 3 份研究报告/月；"steal this idea"模式下同质化、易撞车 |
| **FounderPal** | solopreneur | 核心 idea 生成器**完全免费、免注册** | 通用 LLM | 10 秒出 10 条 idea、User Persona 生成器、营销策略 | 纯 LLM、无真实数据、输出泛化、需大量人工精修 |
| **Buildpad** | 做产品的 founder | 订阅制（含免费档） | AI + 行业问题头脑风暴 | 选定行业内 20 条 idea、市场研究、产品验证流程 | 偏"陪跑式工作流"，深度依赖 LLM 推理，市场数据实时性弱 |
| **GummySearch** | 创业者 / 营销 / 内容 | 曾 $29–$199/mo | Reddit（13 万+ 活跃 subreddit） | 自动归类 Pain Points / Solution Requests / Money Talk / Hot Discussions、关键词追踪 | **已于 2025-11-30 停止新签与续费**——未拿到 Reddit 商业 API 授权而关停 |
| **Glasp** | 学习者 / 研究者 / 写作者 | 免费档；Premium 约 $9/mo | 用户自己的高亮 + 社区高亮 | 网页/PDF/YouTube 高亮、AI clone 写作、社区发现 | 不是 idea 工具本体，而是"知识沉淀 + 发现"层；idea 生成是副产品 |
| **idea 验证类**（WorthBuild / IdeaProof / Validator AI / ProductGapHunt / ValidateMySaaS） | 验证阶段 founder | WorthBuild $5/报告；IdeaProof €19.99–99.99/mo；Validator AI $49/3 通话 | Google Trends + Reddit + HN + 融资库 / 50+ 源 / 竞品评论(G2,Trustpilot) | 0-100 评分、TAM/SAM/SOM、单位经济、SWOT、竞品表 | "广度牺牲深度"、偏 AI 推理而非实时数据、"无法替代真人访谈" |

> 来源核实：IdeaBrowser 价格经 WebFetch 确认为 Starter $299/yr、Pro $999/yr（页面仅列年付）；GummySearch 关停原因经 WebFetch 确认为 Reddit 商业 API 授权失败。

---

## 二、按维度的格局分析

### 1. 它们各自切了哪一"源"？

把竞品映射到你最终目标的三源框架：

| 你的三源 | 对应竞品 | 缺口 |
|---|---|---|
| **外部事件变化** | Exploding Topics、TrendHunter | 多为"趋势词/宏观信号"，离"可执行 idea"还有一步 |
| **用户脑内迸发的 idea** | IdeaBrowser、FounderPal、Buildpad | 几乎全是纯 LLM 头脑风暴，缺真实信号锚定 |
| **模拟目标人群痛点分析** | GummySearch（已死）、WorthBuild 数据侧 | 痛点挖掘最依赖 Reddit，恰恰是最脆弱的一环 |

**关键发现：没有一家做三源融合。** 趋势工具不生成 idea，idea 工具不接真实信号，痛点工具刚因平台政策死掉。你的系统价值正在于"把三源拼成一条每日稳定产出的流水线"。

### 2. 定价区间与商业模式

- **低端免费引流**：FounderPal（免费免注册）、IdeaBrowser Free（每日 1 条）—— 都是 lead magnet / 漏斗顶。
- **中端订阅 $79–$299/yr**：Exploding Topics Entrepreneur、IdeaBrowser Starter —— 面向认真的 solo founder。
- **高端 $199/mo 以上**：Exploding Topics Investor、TrendHunter PRO —— 面向投资人 / 企业。
- **社群溢价**：IdeaBrowser Empire 把"教练 + AMA + 社群 + 工具优惠"打包，本质卖的是"陪伴感与确定性"，而非数据。

> 启示：纯数据/生成的支付意愿在被 LLM 平民化快速压低；高客单价正从"数据"转向"社群 + 验证确定性"。

### 3. 共性差评（即机会）

1. **输出同质化**：纯 LLM idea generator 被批"千篇一律"，甚至"自信地报出无法核实的 TAM 数字"。
2. **数据源单点风险**：GummySearch 之死是教科书案例——重度依赖单一平台 API，政策一变即归零。
3. **生成 ≠ 验证**："2026 年创造成本暴跌，好 idea 易得、已验证需求稀缺"；验证工具自身也承认"无法替代真人访谈"。
4. **强制年付与不透明计费**：Exploding Topics 有多起投诉。
5. **利基覆盖浅**：趋势工具在细分赛道数据稀薄。

---

## 三、差异化机会

1. **三源融合的"每日 idea 流水线"是空白市场**。竞品要么只做趋势、只做生成、只做痛点。idea-factory + idea-evl 的组合天然就是"信号 → 生成 → 评估"全链，且能跨源交叉验证（趋势 + 痛点同时命中 = 高分）。

2. **多数据源冗余 = 抗平台风险的护城河**。GummySearch 死于 Reddit 单点。你的 collect.py 已支持 HN / Product Hunt / RSS 三源；继续保持"任一源失效不致命"的多源架构，本身就是相对竞品的结构性优势。

3. **把"验证确定性"产品化（idea-evl 的定位）**。市场已证明：评估打分（0-100 评分、TAM/SAM/SOM、单位经济、竞品聚合）有真实付费意愿（WorthBuild $5/报告、IdeaProof €19.99+/mo）。但它们的通病是"偏 AI 推理、缺真实数据"。idea-evl 若把评分**强制锚定到 idea-factory 采集的真实信号证据**（哪条 HN 帖、哪个 PH 发布、信号新鲜度），就能直接打中"AI 验证太虚"的最大差评。

4. **"信号新鲜度"作为差异化卖点**。Exploding Topics 的价值就是"早"。一人公司的 LLM agent 流水线可以做到每日刷新，避开企业级工具的慢周期。

---

## 四、对 idea-factory / idea-evl 的具体借鉴 / 可落地建议

### 给 idea-factory

1. **正交化数据源、设计降级路径**。借鉴 GummySearch 教训：在 `collect.py` 中为每个源做显式的"失效隔离"——任一源拿不到数据时，pipeline 仍能用其余源跑完。可在归一化记录里加 `source_reliability` / `last_success_at` 字段，便于监控。
2. **给信号打"新鲜度 + 增长性"标签**，对标 Exploding Topics 的"增长曲线"。在 `normalize.py` 输出里加入 `signal_age_days` 和（若可得）`momentum`（如 HN 分数增速、PH 当日票数），这是后续评分的关键输入。
3. **"痛点类型"分类借鉴 GummySearch**。它把帖子自动归为 Pain Points / Solution Requests / Money Talk / Hot Discussions。在 `generate.py` 之前加一个轻量分类步骤（关键词/正则即可，保持离线契约），让 idea 候选携带"它解决的是哪类痛点"。`match.py` 已做关键词匹配，可在此基础上扩展类别标签。
4. **坚守离线 demo 契约**。以上全部可在离线 sample 数据上实现，真实 API 仍仅在 opt-in `collect` 路径触发——符合 CLAUDE.md 硬规则，不引入新网络调用到 demo 路径。
5. **三源框架对齐**。当前主要覆盖"外部事件"源；"用户脑内 idea"可设计为一个本地输入文件（如 `data/raw/user_ideas.json`），"模拟人群痛点"可由 LLM 在评估阶段生成 persona——为最终三源融合预留数据形状。

### 给 idea-evl（当前空仓）

1. **以"证据锚定评分"为第一原则建仓**。直接对标 WorthBuild / IdeaProof 的评分维度，但每一项分数都必须引用 idea-factory 产出的具体信号 ID 作为证据，避免"AI 编 TAM"的通病。建议初版评分维度：需求信号强度、信号新鲜度、竞争密度、可执行性、一人公司可行性（solo-founder fit）。
2. **输出"0-100 总分 + 分维子分 + 证据链"**，而非黑箱单分。IdeaProof 的 SWOT、WorthBuild 的 TAM/SAM/SOM 可作为子模块参考。
3. **模拟人群痛点分析放在 idea-evl 侧**。用 LLM 生成"目标 persona + 其痛点强度"作为评分输入——这是 GummySearch 死后留出的空缺，且不依赖任何脆弱的第三方 API。
4. **复用 idea-factory 的 export 模式**（JSON + Markdown 双产出），保持两仓数据契约一致，便于"factory 产出 → evl 消费"的管道串联，最终凑齐"每天 10–20 条经筛选 idea"目标。

### 一人公司"自建 vs 订阅"取舍

| 维度 | 自建（idea-factory/evl） | 订阅竞品 |
|---|---|---|
| 成本 | 主要是你的时间；2026 vibe coding 已大幅降低自建成本 | $79–$199/mo 起，叠加多个工具很快超 $500/mo |
| 数据控制 | 完全掌握、可多源冗余、可二次加工 | 受平台 API 政策摆布（GummySearch 殷鉴） |
| 三源融合 | 唯一能定制实现 | 没有现成产品 |
| 维护负担 | 需自己维护采集器与 LLM 成本 | 开箱即用 |

**建议**：核心、需每日反复运行、且是你业务命脉的环节（采集 + 评分流水线）→ **自建**（Fast Company 的 solopreneur build-vs-buy 框架："会反复做且触及核心业务的，DIY"）。一次性 / 非核心的对照参考（如某条趋势的宏观验证）→ 可临时**订阅** Exploding Topics 单月做交叉校验，而非长期绑定。

---

## 参考链接

- Exploding Topics 工作原理与数据源（Semrush KB）：https://www.semrush.com/kb/1490-exploding-topics
- Exploding Topics 定价（Toolsurf）：https://www.toolsurf.com/exploding-topics-pricing-2025-plans-features-and-is-it-worth-it-2026-plans-features-best-deals-compared/
- Exploding Topics 差评/局限（Trustpilot）：https://www.trustpilot.com/review/explodingtopics.com
- Exploding Topics 综合评测：https://www.toolsurf.com/exploding-topics-review-a-comprehensive-review-2026/
- IdeaBrowser 定价页：https://www.ideabrowser.com/pricing
- IdeaBrowser 定价核实（SwipeFile）：https://swipefile.com/ideabrowser-free-starter-and-pro-pricing-page
- IdeaBrowser 作为 lead magnet 解析（Startup Spells）：https://startupspells.com/p/greg-isenberg-ideabrowser-lead-magnet-wantrepreneurs-startup-ideas-podcast/
- Greg Isenberg 推文（免费 1 idea/天）：https://x.com/gregisenberg/status/1939401459851985356
- GummySearch 产品页：https://gummysearch.com/product/
- GummySearch 关停与替代品（Reddinbox）：https://reddinbox.com/blog/best-gummysearch-alternative
- GummySearch 关停替代品（KarmaGuy）：https://karmaguy.io/en/blog/gummysearch-alternatives
- FounderPal 评测/定价：https://www.aiapps.com/items/founderpal/
- FounderPal 工具页：https://mavtools.com/tools/founderpal-ai/
- Buildpad 评测：https://aibox100.com/tools/buildpad
- TrendHunter 定价/方案：https://www.trendhunter.com/plans
- TrendHunter 创新者解决方案：https://www.trendhunter.com/trendreports
- Glasp 定价：https://glasp.co/pricing
- Glasp 评测/替代品（OpenTools）：https://opentools.ai/tools/glasp
- 创业 idea 验证工具对比（WorthBuild，对位 idea-evl）：https://worthbuild.io/blog/best-startup-idea-validation-tools-2026-comparison
- AI 验证工具实测对比（Trend Seeker）：https://trend-seeker.app/blog/idea-validation-tools
- solopreneur 自建 vs 订阅决策（Fast Company）：https://www.fastcompany.com/91494674/the-solopreneurs-build-vs-buy-decision
- 市场情报工具与真实定价（Prospeo）：https://prospeo.io/s/market-intelligence-tools
