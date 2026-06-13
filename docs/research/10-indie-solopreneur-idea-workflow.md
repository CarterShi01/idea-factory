# 一人公司 / 独立开发者视角：系统化找 idea 的工作流与人机协作落地

> 调研目标：indie hacker / solopreneur 如何系统化地发现并验证创业 idea，并结合用户"软件为主、兼顾投资"的身份，设计一套**每天 30-60 分钟人工介入即可消化 10-20 条 idea** 的人机协作流程。核心隐喻：**像看 deal flow 一样看 idea flow**。

---

## 一、独立开发者真实的"找 idea"工作流长什么样

调研 IndieHackers、Pieter Levels（levelsio）、build in public 社区后，可以把主流做法收敛成三种**互补**的路径，而不是相互替代：

| 路径 | 代表人物/方法 | 信号来源 | 优点 | 风险 |
|---|---|---|---|---|
| **Scratch your own itch（挠自己的痒）** | Pieter Levels（NomadList / RemoteOK） | 自己每天遇到的真实痛点 | 至少 1 个真实用户（你自己）、能判断方案有效性、零调研成本 | 样本=1，容易做出"只有我需要"的东西 |
| **Pain mining（痛点挖掘）** | IndieHackers 社区、Reddit/HN 抓取流 | 社区里**反复出现**的同一抱怨 | 需求可被外部验证、可量化频次 | 噪声大，需要去重和聚合 |
| **Event-driven（事件驱动）** | Product Hunt / HN 新发布、平台政策变化 | 新产品发布、API 开放、监管/平台变动 | 抓"时间窗口"，先发优势 | 容易追热点、同质化竞争激烈 |

**关键洞察一**：这恰好对应用户最终目标里的三个源头——【外部事件变化】≈ event-driven，【脑海里迸发的 idea】≈ scratch your own itch，【模拟目标人群痛点分析】≈ pain mining。三者**不是要选一个，而是要并行采集再统一进入同一条评估管线**。

**关键洞察二（Pieter Levels 的方法论）**：他的"12 startups in 12 months"核心不是"idea 多牛"，而是**强制 ship + 用市场结果当验证器**。创意工作者的通病是"永远做不完、做完忘了发"。他把每个项目压缩到 1 个月、必须 launch，然后**让真实流量/收入来决定哪个值得继续**。失败的大多数被快速放弃，NomadList、RemoteOK 这类跑出来的靠的是**留存和付费这种行为数据，而不是事前的"好点子感觉"**。

> 对本系统的直接启示：idea-factory 不应追求"产出完美 idea"，而应**产出足够多、结构化、可快速验证的候选**，把"哪个靠谱"交给后续轻量验证和市场，而不是在生成阶段过度纠结。

---

## 二、idea validation 的可落地"评分卡"（idea-evl 的直接素材）

社区里 idea validation 已经高度模板化。我核实了一个被引用较多的 **23 点验证清单 / 5 大类**（IdeaKiller 等多处口径一致），它几乎可以直接变成 idea-evl 的打分 schema：

| 类别 | 关键检查项（节选） | Kill / Caution Gate |
|---|---|---|
| **市场需求 Market Demand (6)** | 问题相关查询月搜索量 >100；Google Trends 5 年内稳定或上升；≥3 个社区在讨论该痛点；TAM >\$100M；已有 willingness-to-pay 信号（用户已在为 workaround 付费） | 命中 <3 项 = 需求不足，直接 kill |
| **竞争格局 Competitive (5)** | 找出 3-5 个直接/间接竞品；从评论中提取竞品具体缺陷；差异化可防守（不能只是"UX 更好"）；无单一玩家占 >70% 份额 | — |
| **问题-市场契合 (5)** | 用一句话定义 ICP；痛点高频（至少每周/每天发生）；现有方案明显不足；有付费意愿证据；切换成本足够低 | 命中 <3 项 = 弱契合 |
| **单位经济 Unit Economics (4)** | LTV:CAC ≥ 3:1；CAC 回收 <12 个月；毛利 >60%；12-18 个月可盈亏平衡 | LTV:CAC <2:1 = 商业模式需重做 |
| **风险与可行性 (3)** | MVP 可在 3 个月内做出；无监管/合规阻碍；识别 Top5 失败模式及缓解 | — |

**总分判定**：19-23=强烈 proceed；14-18=补齐缺口再投入；8-13=需 pivot；0-7=放弃。

> 对 idea-evl 的价值：这是一套**带 kill gate 的加权评分卡**，非常适合作为 evl 的 v1 rubric。重点是它把"需求是否真实"放在第一关并设硬性 kill gate——契合下文"投资视角"。

**验证手段的可自动化部分**（demand 优先于 solution 优先于 supply）：
- **可自动取信号**：搜索量/Trends、社区讨论帖数、竞品数量与评论差评聚类、是否已有付费 workaround。这些都能由 agent + API/抓取离线/半离线完成。
- **需人工或轻量实验**：smoke test（落地页+广告点击率）、concierge / Wizard-of-Oz、客户访谈。这些**不应由系统替人做决定**，而是系统**生成实验建议**、人去执行。

---

## 三、像看 deal flow 一样看 idea flow（投资视角，核心创新点）

用户兼做投资，这是本系统最该借鉴的心智模型。VC/天使的 deal flow 管线是：**sourcing → screening → due diligence → negotiation → closing**，每一阶段都是**漏斗式过滤**，而且投资人**靠"量"来保证能命中少数赢家**（一个健康的 deal flow = 稳定、高质量的机会流）。

把它平移到 idea flow：

| Deal Flow 阶段 | 对应 idea flow 阶段 | 谁来做 |
|---|---|---|
| Sourcing（找项目） | 三源采集：事件/自有 idea/痛点模拟 | **系统**（collect.py + 新增源） |
| Screening（初筛打分） | 评分卡自动打分 + kill gate | **系统**（idea-evl） |
| Due diligence（尽调） | 拉竞品、搜索量、付费证据、生成验证实验建议 | 系统取数 + **人看摘要** |
| IC / 决策 | 决定 pursue / park / kill | **人**（每天 30-60 分钟） |
| Portfolio mgmt | 跟踪已 pursue 的 idea，复用信号 | 系统提醒 + 人复盘 |

**投资视角带来的三条原则：**
1. **量是前提，不是负担**。投资人一年看几百个项目投几个；用户每天看 10-20 条、最终亲自下场 1-2 个/月完全正常。系统的职责是**保证流量稠密且去过噪**。
2. **kill 比 pursue 更重要**。deal flow 软件的核心是 screening 和 scoring，让你**快速说不**。idea-evl 的第一价值是"高效淘汰"，而不是"找出唯一神 idea"。
3. **管线要有 CRM/状态**。投资人用 Airtable/Notion 跟踪每个 deal 的 stage、tag、score。idea-factory 的输出应带 **stable id + 状态字段（new/screened/diligence/pursue/parked/killed）**，让 idea 可被持续跟踪而非每天重新生成。

---

## 四、每天 30-60 分钟的人机协作流程设计

目标：系统每天产出 10-20 条**已初筛+已打分**的 idea，人只做"投资人式决策"。

**系统每天自动产出（无人值守）：**
1. **采集**（collect.py 扩展）：HN/PH 新发布、目标 subreddit/社区痛点、用户自己随手记的 idea inbox（一句话即可）。
2. **归一化 + 去重**（normalize.py + match.py）：把三源信号统一成结构化记录；用关键词/语义匹配**对已有 idea 做去重和聚合**（避免每天看到同一个痛点的 30 个变体）。
3. **生成候选**（generate.py）：每条信号 → 结构化 idea（ICP 一句话、痛点频次、假设的 willingness-to-pay、最近似竞品、MVP 工作量估计）。
4. **评分 + kill gate**（idea-evl）：套用第二节评分卡，自动算总分并标记 kill gate 命中情况，**按分数排序**。
5. **产出 Digest**：一份 Markdown 日报——Top 10-20，每条 ≤5 行：一句话 idea / ICP / 关键信号证据 / 评分与红旗 / 系统建议的下一步验证动作。

**人每天做的（30-60 分钟，纯决策）：**
- 扫 digest，对每条做**一个动作**：`pursue` / `park`（存入 watchlist 等更多信号）/ `kill`（带一句理由，喂回系统改进过滤）。
- 对 1-2 条 `pursue` 的，执行系统建议的**一个**轻量验证动作（发个落地页、问 3 个目标用户、查一次真实搜索量）。
- 每周一次：回看 watchlist，看是否有 idea 因新信号（事件/竞品动向）升温——这正是 event-driven 复用。

**关键设计：人决策什么 vs 系统决策什么**
- 系统决策：采集、去重、结构化、评分排序、生成验证建议——**全是可量化、可重复的脏活**。
- 人决策：pursue/kill/park 的**判断**、以及"我愿不愿意亲自做/投这个"的**主观品味**——这是无法外包的部分，正好对应"scratch your own itch"里只有创始人自己能判断的"这事我在不在乎"。

---

## 五、对 idea-factory / idea-evl 的具体借鉴 / 可落地建议

**对 idea-factory：**
1. **把三源统一进同一条管线**。当前 collect.py 已支持 HN/PH/RSS；建议显式新增第三类输入——一个极简的"**idea inbox**"（用户随手记的一句话 idea，离线读本地文件即可，不破坏 offline demo 契约），以及"痛点模拟"源（先用本地样本/抓取的社区帖，后续接 LLM 做痛点聚类）。三源进入同一 normalize → generate。
2. **去重/聚合是刚需**，否则 10-20 条会被同质信号污染。强化 match.py：从"匹配 fresh 信号 vs 已有 idea"扩展到"**对当天候选内部去重 + 聚类**"，避免一个痛点产出 N 条近似 idea。
3. **给 idea 加稳定 id + 状态字段**（new/screened/diligence/pursue/parked/killed）。这是把"每天重新生成"变成"可跟踪 idea flow"的最小改动，对应投资人的 deal CRM。输出端 export.py 增加一个"每日 Digest（Top N + 红旗 + 建议动作）"格式。
4. **生成阶段不要追求完美**。借鉴 Pieter Levels：宁可多生成、结构化好，把筛选交给 evl 和人。generate.py 应为每条候选补齐评分卡所需字段（ICP 一句话、痛点频次估计、近似竞品、MVP 工作量）。

**对 idea-evl（当前空仓，正好从零设计）：**
1. **v1 直接落地"5 大类 + kill gate"评分卡**（本报告第二节），输出：总分（0-23）、各类得分、命中的 kill/caution gate、一句话结论（proceed/补缺/pivot/abandon）。
2. **优先实现"快速淘汰"而非"精准选优"**。第一关 = 需求验证 kill gate（搜索量/社区讨论/付费 workaround <3 项即 kill），这能挡掉大量噪声，让人每天只看真正过关的。
3. **区分"可自动取数的分"与"需人工/实验的分"**。自动分（搜索量、竞品数、差评聚类）由 evl 直接算；需实验的分（smoke test 转化、访谈）由 evl **生成"建议的验证动作"占位**，待人回填，避免系统假装自己知道付费意愿。
4. **把人的 kill 理由回流**当训练/规则信号，逐步让评分卡贴合用户个人的"投资品味"（软件为主、能一人维护、毛利高、MVP <3 个月）。

**一句话总结**：idea-factory = 你的 idea sourcing + screening 漏斗，idea-evl = 你的带 kill gate 的尽调评分卡，人 = 每天 30-60 分钟的"投资委员会"，只做 pursue/park/kill 三选一。系统保证**流量稠密、去噪、结构化、可跟踪**，人只贡献无法外包的**品味与决策**。

---

## 参考链接

- [Pieter Levels — I'm Launching 12 Startups in 12 Months (levels.io)](https://levels.io/12-startups-12-months)
- [12 Startups in 12 Months 标签页 (levels.io)](https://levels.io/tag/12-startups-in-12-months/)
- [Turning side projects into profitable startups (levels.io)](https://levels.io/startups)
- [Market research and idea validation process — Indie Hackers](https://www.indiehackers.com/post/market-research-and-idea-validation-process-1e1830ba35)
- [How to validate a startup idea — Indie Hackers](https://www.indiehackers.com/post/how-to-validate-a-startup-idea-34f9df9d6b)
- [Don't Waste $20k: A 4-Step Checklist for Validating Your Startup Idea — Indie Hackers](https://www.indiehackers.com/post/dont-waste-20k-a-4-step-checklist-for-validating-your-startup-idea-8f91e23f40)
- [Ideas are cheap. Here's how to validate them. — Indie Hackers](https://www.indiehackers.com/post/ideas-are-cheap-heres-how-to-validate-them-80280c4c9c)
- [How to Come Up With Profitable Ideas as an Indie Hacker — Wisp CMS](https://www.wisp.blog/blog/how-to-come-up-with-profitable-ideas-as-an-indie-hacker)
- [Startup Idea Validation Checklist (2026) — The 23-Point Framework — IdeaKiller](https://ideakiller.app/blog/startup-idea-validation-checklist/)
- [Startup Idea Validation: Prove Demand Before You Build — KIIC](https://kiic.in/startup-idea-validation/)
- [How to Validate a Startup Idea in 2026 (The Old Playbook Is Dead) — Andrés Max](https://andresmax.com/validate-startup-idea/)
- [How to Build a Startup Deal Flow Pipeline — Allied Venture Partners](https://www.allied.vc/guides/how-to-build-a-startup-deal-flow-pipeline)
- [Navigating the Deal Flow in Angel Networks — FasterCapital](https://fastercapital.com/content/Navigating-the-Deal-Flow-in-Angel-Networks.html)
- [Deal Flow Management Software: What to Look For in 2026 — Startup Science](https://www.startupscience.io/articles/deal-flow-management-software)
- [Auto-generate MVP startup ideas from Reddit with AI — n8n workflow template](https://n8n.io/workflows/3824-auto-generate-mvp-startup-ideas-from-reddit-with-ai-and-excel-storage/)
- [How I use Reddit and AI to find winning startup ideas (2025) — Alexander F. Young](https://blog.alexanderfyoung.com/how-i-use-reddit-and-ai-to-find-winning-startup-ideas-2025-tutorial/)
- [Show HN: Tool that generates startup ideas with AI by scanning Reddit — Hacker News](https://news.ycombinator.com/item?id=40061899)
- [Portfolio Entrepreneurship Guide: Strategies for Success 2025 — Swisspreneur](https://www.swisspreneur.org/blog/portfolio-entrepreneurship)
