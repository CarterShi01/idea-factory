# 自动化创业 idea 生成/发现：开源项目与产品全网调研

> 调研范围：与 idea-factory（信号采集→归一化→生成 idea→筛选）目标高度一致的**开源仓库与商业产品**。重点回答三个问题：(1) 有没有可直接 fork/参考的近似仓库；(2) 它们的 pipeline 如何设计；(3) 各自的局限与对 idea-factory / idea-evl 的可落地借鉴。

## 一、结论速览

1. **存在一个目标几乎完全对齐的开源仓库**：`MaxKmet/idea-validation-agents`（MIT，约 266 star）。它把"多源信号采集 → 生成评分 idea → 九步验证 → 评分裁决（0-100）"做成了一套可被 Claude Code/Cursor 直接驱动的 agent 工作流，且产物落地为 `ideas/scores.json`、`decision_memo.md` 等结构化文件。**这恰好覆盖了 idea-factory + idea-evl 两个仓库合起来想做的事**，是当前最值得逐文件拆解参考（而非整体 fork）的对象。
2. **商业产品已经验证了"信号→idea→评分"这条产品形态的市场需求**：IdeaBrowser（每日 Idea of the Day）、IdeaPicker、PainHunt、PainBase、GummySearch（已于 2025-11 因 Reddit API 商用授权失败关停）。它们共同证明：**真实社区抱怨（Reddit/HN）是最高信噪比的 idea 源头**，且用户愿意为"评分+决策备忘"而非"裸 idea 列表"付费。
3. **纯开源的"端到端每天产出 10-20 条靠谱 idea"的成熟仓库基本不存在**。开源侧多为"半成品零件"：信号采集器（reddit-saas-idea-finder、RedditMiner）、LLM 抓取器（llm-scraper、ScrapeGraphAI/Firecrawl）、agent 框架（CrewAI/LangGraph）。idea-factory 的真正机会是**把这些零件按一条评分明确的流水线组装起来**。

## 二、近似/可参考的开源仓库对照表

| 项目 | Star | 做法（pipeline） | 可借鉴点 | 与 idea-factory 的差距 |
|---|---|---|---|---|
| **MaxKmet/idea-validation-agents** | ~266 | 四工作流：背景访谈→趋势分析→7-10 条**带评分**的 idea；再走九步验证（竞品/定价/分发/留存/CAC）→ 0-100 裁决。多源：TikTok Creative Center、Reddit、App Store、Google Trends | 评分用**乘法-下限算法**（致命短板直接归零）；RAT（≤2 周/≤$100 实验）；产物落地 `scores.json`/`decision_memo.md` | 它是"prompt 配置驱动"，无离线 demo、无 Python 流水线代码；信号采集靠 agent 实时抓取，不是 idea-factory 的 collect.py 形态 |
| **Nacorga/reddit-saas-idea-finder** | 小 | 关键词搜 Reddit→抓标题/正文/评论→识别"挫败/未满足需求/昂贵方案"信号→存 `data.json` | 与 idea-factory 的 collect.py + match.py 思路**几乎同构**，可直接对照其关键词信号词典 | 只到"信号"层，无生成、无评分、无 Markdown 报告 |
| **RedditMiner** | 小 | 抓 Reddit→批量生成 idea→导出干净 `.md` | "批量生成 + Markdown 导出"正是 idea-factory 的 export.py 目标 | 单源、无打分、无归一化层 |
| **mishushakov/llm-scraper** | 较高 | 任意网页→LLM 抽成结构化数据（示例即抓 HN top stories） | 可作为 collect.py 中 HN/PH 抓取的"网页→结构化"替代实现 | 是底层工具，不是 idea pipeline |
| **ScrapeGraphAI / Firecrawl** | 高（Firecrawl ~130K） | 基于 LangChain 的图式抓取/搜索/抽取 | 若未来要扩信号源，做"抓取层"的工业级替代 | 与 idea 生成/评分无关 |
| **CrewAI / LangGraph** | 52K+ / 33K+ | 多 agent 角色协作 / 有状态可控 agent | 若 idea-evl 要做"多评委打分"可用，但**CLAUDE.md 明确把"复杂多 agent 框架"列为非目标**，谨慎 | 框架本身不含业务逻辑 |
| **wanshuiyin/Auto-claude-...research-in-sleep (ARIS)** | ~12K | 自主 ML 研究：跨模型评审环 + idea 发现 + 实验自动化 | "跨模型评审环"思路可迁移到 idea-evl 的多模型交叉打分 | 面向科研 idea，非创业 idea |
| **ScholarScout / IdeaMiner / SciAtlas** | 27/9/126 | 论文/知识图谱→研究 idea | "结构化知识源→idea"范式 | 学术语料，与市场信号不对口 |

**关于 fork：** 没有一个仓库适合"整体 fork 当底座"。最优策略是 **fork 不必、逐文件借鉴必须**——把 `idea-validation-agents` 的**评分算法与验证清单**、`reddit-saas-idea-finder` 的**信号词典**搬进 idea-factory/idea-evl 的现有 src 结构。

## 三、商业产品的 pipeline 拆解（验证过的产品形态）

| 产品 | 信号源 | 生成 | 评分/筛选维度 | 关键产品决策 |
|---|---|---|---|---|
| **IdeaBrowser** | Reddit 帖、搜索量、社区信号 | "AI 研究 agent" 把 50+ 小时研究压成 10 分钟读物 | 市场规模、竞争、收入潜力、执行难度、GTM、**创始人匹配（技能/资本/时间）** | **Idea of the Day**：每天一条精研 idea——与"每天稳定产出 10-20 条"的目标直接呼应 |
| **IdeaProof** | Web 搜索 + 专利库 + 市场数据 API | <3 分钟出评估 | **五维加权**：市场规模增长 25% / AI 防御力 25% / 收入潜力 20% / 启动成本与速度 15% / 创始人可达性 15% | 明确区分"真垂直 AI 机会"vs"ChatGPT 套壳" |
| **IdeaPicker** | 250+ subreddit | 三段式 Scan→Identify（把问句抽象成痛点）→Generate（产品/市场/变现/月收入预估） | AI 痛点分析 + 月收入预估 | 25,000+ idea 库；显式声明收入预估**不保证准确**（合规护栏） |
| **PainHunt** | 26 个平台 24/7（Reddit/HN/X/App Store/Google Play…） | 关键词→10 秒验证 | 高频抱怨聚合排名 | 多源 + 速度作为卖点 |
| **GummySearch** | Reddit | AI 聚类相似问题→摘要 | 痛点频次/趋势 | **2025-11 关停**，原因：未获 Reddit Data API 商用授权——对 idea-factory 是合规警示 |

**跨产品共性（强信号）**：
- 信号源高度集中在 **Reddit + HN + App Store + Google Trends**，因为"真实抱怨 ≈ 真实需求"，优于问卷。
- 几乎都用 **5 维左右的加权评分**，且都强调 **GTM 与创始人匹配**（idea-factory 当前 ranks.py 大概率缺这两维）。
- 产物从"裸 idea"升级为"**决策备忘 + 评分**"。
- **致命短板一票否决**（IdeaProof 的"防御力"、idea-validation-agents 的乘法-下限）比简单加权更接近"靠谱"。

## 四、对 idea-factory / idea-evl 的具体借鉴/可落地建议

**给 idea-factory（信号→生成）：**
1. **信号词典对照升级**：把 `reddit-saas-idea-finder` 的"frustration / unmet need / expensive solution"信号词搬进 `match.py` 的关键词集，提升 collect.py 抓回信号的命中质量。这是离线、零网络风险的纯逻辑改动。
2. **三段式归一化**：借 IdeaPicker 的 Scan→Identify→Generate。在 `normalize.py` 增加一层"问句/抱怨 → 抽象痛点"的归一化字段（pain_statement），让 `generate.py` 基于痛点而非原始标题生成，质量更高。
3. **沿用 mishushakov/llm-scraper 的"网页→结构化"范式**为 collect.py 的 HN/PH 解析做 schema 化抽取（仍保持 opt-in、不进离线 demo 路径）。
4. **对齐"每日产出"形态**：参考 IdeaBrowser 的 Idea of the Day，让 pipeline 的 export 支持"每日 N 条"的 Markdown 摘要格式（与 export.py 现有 JSON/Markdown 兼容）。

**给 idea-evl（评估→打分，当前空仓）：**
5. **直接采用 5 维加权评分骨架**，建议初版：市场规模/增长、问题严重度（pain severity）、可行性与启动成本、收入潜力、创始人匹配（这位用户是一人软件公司，"创始人可达性/技能匹配"权重应高）。可直接借 IdeaProof 的权重做初值。
6. **引入"致命短板一票否决"**：采用 idea-validation-agents 的**乘法-下限**而非纯加权——任一维过低则总分坍塌，天然过滤"看着不错但有硬伤"的 idea，契合"靠谱"目标。
7. **输出决策备忘而非分数**：仿其 `scores.json` + `decision_memo.md` 双产物。idea-evl 读 idea-factory 的 JSON，输出 `scores.json`（机器可读，供排序）+ `decision_memo.md`（人读，含 RAT 实验建议）。
8. **RAT 落地实验作为筛选闸门**：每条进入"靠谱"清单的 idea 附一个 ≤2 周、≤$100 的最小验证实验，把"评估"前移为"可验证假设"，比纯打分更可执行。
9. **多模型交叉评审（可选、需克制）**：ARIS 的跨模型评审环可迁移为 idea-evl 的双模型打分取一致性，但须遵守 CLAUDE.md 对"复杂多 agent 框架"的非目标约束，建议先用单模型、留接口。

**合规与边界提醒**：GummySearch 因 Reddit API 商用授权关停。idea-factory 的 collect.py 抓 Reddit/HN 须坚持 opt-in、尊重各站 API 条款，且**不进离线 demo 路径**（与 CLAUDE.md 一致）。评分中的"月收入预估"应像 IdeaPicker 一样显式标注不保证准确。

## 五、一句话路线

不要 fork 任何单一仓库；把 **idea-validation-agents 的评分/验证逻辑** 注入 idea-evl，把 **reddit-saas-idea-finder/IdeaPicker 的痛点信号与三段归一化** 注入 idea-factory，对齐 IdeaBrowser 的"每日产出 + 决策备忘"形态，即可用最小改动逼近"每天 10-20 条经初筛的靠谱 idea"目标。

## 参考链接

- idea-validation-agents（最接近的开源仓库）: https://github.com/MaxKmet/idea-validation-agents
- GitHub idea-generation 话题页: https://github.com/topics/idea-generation
- reddit-saas-idea-finder: https://github.com/Nacorga/reddit-saas-idea-finder
- mishushakov/llm-scraper: https://github.com/mishushakov/llm-scraper
- ScrapeGraphAI Hackathon repo: https://github.com/ScrapeGraphAI/Scrapegraph-LabLabAI-Hackathon
- Firecrawl: https://www.firecrawl.dev/
- IdeaBrowser 评测（含 Idea of the Day）: https://aipure.ai/products/ideabrowser-com
- IdeaBrowser→Google Docs 的 n8n 工作流模板: https://n8n.io/workflows/4901-daily-business-idea-insights-aggregator-from-ideabrowser-to-google-docs/
- IdeaProof（五维加权评分）: https://ideaproof.io/lists/ai-startup-ideas
- IdeaPicker（三段式 Scan/Identify/Generate）: https://skywork.ai/skypage/en/ideapicker-ai-reddit-ventures/1977559157453557760
- IdeaPicker 工具页: https://topai.tools/t/ideapicker
- PainHunt（26 平台 24/7）: https://painhunt.dev/
- PainBase: https://www.painbase.space/
- GummySearch 产品页: https://gummysearch.com/product/
- GummySearch 起源/商业（Starter Story）: https://www.starterstory.com/stories/gummysearch
- "用 Reddit + AI 找创业 idea" 教程: https://blog.alexanderfyoung.com/how-i-use-reddit-and-ai-to-find-winning-startup-ideas-2025-tutorial/
- 用 Reddit 与 GitHub 验证 SaaS idea（DEV）: https://dev.to/iamvs2002/how-developers-can-validate-saas-ideas-using-reddit-and-github-3b0l
- awesome-ai-agents-2026（框架全景）: https://github.com/ARUNAGIRINATHAN-K/awesome-ai-agents-2026
- 最佳开源 agent 框架（Firecrawl 博客）: https://www.firecrawl.dev/blog/best-open-source-agent-frameworks
