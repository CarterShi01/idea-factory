---
doc: research
lane: L5
title: "enrich:取证研究 agent 与网页抓取"
date: 2026-07-07
agent: subagent
---

# L5 enrich:取证研究 agent 与网页抓取

## 结论速览

Top 3:**gpt-researcher**(deep-research 流程拆解 + "优先含数字来源"的 curation prompt,Apache-2.0)、
**crawl4ai**(只挖它的 `prompts.py`:页面→schema 化 JSON 的证据结构化 prompt 范式 + "LLM 一次生成
CSS schema、之后纯代码复用"的两步抽取模式,Apache-2.0)、**trafilatura**(低频合规取证场景抓取层的
最佳答案:纯 Python、无浏览器、Apache-2.0,是 live fetcher 落地时唯一值得申请的依赖)。

**最重要的一个发现**:crawl4ai 的 `JSON_SCHEMA_BUILDER` 范式(让 LLM 对一个页面模板只花一次钱生成
CSS-selector 抽取 schema,之后同站页面全部纯代码确定性抽取)与我们的成本梯度第一原则天然同构——
竞品定价页/招聘板恰好是"同模板反复取证"的场景,这一个模式就能把 live fetcher 的边际 LLM 成本压到
接近零。另外,deep-research 类 agent 的通病(发散搜索×递归×并行 LLM 调用)对我们是反模式:enrich
是**定向取证**(已知竞品名/岗位关键词→定向 URL),只需借它们的"抓取→curation→带引证结构化"后半段,
砍掉前半段的发散搜索。

## 推荐候选(Top 2–3,按价值排序)

### gpt-researcher
- repository: github.com/assafelovic/gpt-researcher
- stars: ~28k · license: Apache-2.0 · 活跃度: 很活跃(v3.5.1 2026-06-23,71 个 release,3000+ commits,多贡献者)
- mined_for:
  - 数据面: `gpt_researcher/prompts.py`——单文件集中了全部 prompt:`curate_sources`(源筛选,明文要求"prioritize sources containing statistics, numbers, or concrete data"——与我们 `Evidence.numbers` 必填、证据门要数字的设计完全同向,可直接改写成我们的 evidence_structuring prompt 的 curation 段);`generate_search_queries_prompt`(取证查询扩展);报告类 prompt 里的引证强制措辞("You MUST include hyperlinks to the relevant URLs wherever they are referenced")可反哺 L6 diligence 的引证强制。
  - 机制面: ①"planner→并行 per-question 抓取→curation→带源汇总"的四步流程拆解,砍掉 planner 与报告段后,中间两步就是我们单个 Fetcher 的 live 形态(定向 URL 列表→抓取→curation→结构化);②`gpt_researcher/scraper/` 的多后端 scraper 注册表(bs4/browser/tavily/…统一接口按配置切换),与我们 `stages/recall/channels/` 的 adapter 注册表同构,可照此给 Fetcher 加 live/fixture/handoff 后端分叉;③`skills/` 里 curate_sources 作为独立"技能"步骤(抓取与结构化之间插一道便宜的过滤闸)。
- 挖什么: `gpt_researcher/prompts.py`(整文件,重点 curate_sources 与 query 生成);`gpt_researcher/scraper/` 目录结构与各后端接口签名;`gpt_researcher/skills/` 中 source-curation / context 压缩的流程编排;`gpt_researcher/config/` 的 per-step 模型分配约定(便宜模型做 curation、贵模型做汇总——正是成本梯度)。
- SKIP 什么: `multi_agents/`(LangGraph/AG2 编排,重框架)、`backend/`+`frontend/`(FastAPI/NextJS 服务壳)、`mcp-server/`、向量库/memory 部分(我们无 RAG 需求)。
- 坑: 仓库大、LangChain 系依赖深,**只能读不能引**;prompt 与 config 随版本迭代快(71 个 release),钉 commit 挖矿,别追 HEAD;其默认流程按"研究问题"发散多路搜索,直接照搬会在便宜段引爆并行 LLM 调用量。
- recommendation: adopt(登记为参考源,借 prompt+模式,零依赖引入)
- 理由: deep-research 品类的事实标准,prompt 集中单文件可挖性极高,curation prompt 与我们证据门的"要数字"要求天然对齐。
- 与硬约束的冲突: 依赖重(langchain/fastapi)→ 只挖不跑即可规避;其发散搜索×并行抓取诱导每 idea 高 LLM 成本 → 裁剪方式:去掉 planner 发散,固定为"每 Fetcher 一次定向抓取 + 一次便宜 curation + 一次结构化抽取",且只对 rank 幸存者执行(现有漏斗已保证)。

### crawl4ai
- repository: github.com/unclecode/crawl4ai
- stars: ~71k · license: Apache-2.0(attribution 为推荐非强制)· 活跃度: 很活跃(v0.9.0 2026-06-18;近期大量安全修复:RCE/SSRF 等)
- mined_for:
  - 数据面: `crawl4ai/prompts.py` 是本 lane 最直接可 promote 的资产:`PROMPT_EXTRACT_SCHEMA_WITH_INSTRUCTION`(按给定 JSON schema 从页面抽结构化数据——正是"页面→带数字的 Evidence"的 prompt 骨架,套上我们 `Evidence.numbers` 的 schema 即成 evidence_structuring 的机制面 prompt);`PROMPT_FILTER_CONTENT`(HTML→干净 markdown、去导航/广告)可作预处理 prompt;`JSON_SCHEMA_BUILDER`/`JSON_SCHEMA_BUILDER_XPATH`(LLM 生成 CSS/XPath 抽取 schema)。
  - 机制面: ①两步抽取范式:对每个竞品定价页/招聘板模板,LLM **只跑一次** `JSON_SCHEMA_BUILDER` 生成 selector schema,落盘后同站后续取证全走 `JsonCssExtractionStrategy` 式纯代码抽取——把 live fetcher 的边际 LLM 成本降为零,完美贴合成本梯度;②markdown 生成的启发式过滤(pruning + BM25 去噪)是可抄成纯函数的算法,离线可用。
- 挖什么: `crawl4ai/prompts.py`(整文件);`extraction_strategy` 相关模块里 JsonCss/LLM 两种策略的接口划分与 chunking 策略;markdown generation 里 pruning/BM25 content-filter 的算法实现(抄成 stdlib 纯函数)。
- SKIP 什么: 整个 Playwright 浏览器运行时、`deploy/docker/`、`crawl4ai-setup` 安装链、深爬/多页调度器——我们是低频定向取证,不需要浏览器农场。
- 坑: 版本迭代快且 0.x API 常破坏性变更(钉 commit);近期连环安全漏洞说明其服务端形态别碰;文档以"跑起来"为叙事,挖矿时直接读源码而非教程。
- recommendation: adopt(只挖 prompts 与算法,绝不引依赖)
- 理由: 证据结构化(页面→schema 化 JSON)的 prompt 范式最全最精,且两步 schema 抽取模式是全 lane 唯一与成本梯度同构的现成设计。
- 与硬约束的冲突: 重依赖(Playwright)→ 只借 prompt/算法;其 LLM 逐页抽取模式若照搬会每页花贵钱 → 裁剪为"schema 一次生成 + 纯代码复用",LLM 只在新模板首见时介入。

### trafilatura
- repository: github.com/adbar/trafilatura
- stars: ~6.2k · license: Apache-2.0(≥v1.8.0;**更早版本 GPLv3+,只看新版代码**)· 活跃度: 活跃(v2.1.0 2026-06-07,1600+ commits;主要单作者 adbar 维护但持续多年、有学界工业界背书:HuggingFace/IBM/Stanford 等)
- mined_for:
  - 数据面: 无(无 prompt/schema;它是确定性抽取器)。
  - 机制面: ①"低频、少量、合规"取证场景的抓取层答案:纯 Python(+lxml)、无浏览器、内建礼貌抓取,HTML→主内容/markdown/JSON,多项独立评测第一;是 live fetcher 落地时**唯一值得向创始人申请的依赖**(pricing/hiring 页大多是静态 HTML,不需要渲染);②在批准前可借的纯算法:其主内容抽取的启发式(标签密度/正文判定)与姊妹库 htmldate 的**页面日期提取**逻辑——后者直接服务我们 `Evidence.source_date`(24 个月红线依赖可靠的 source_date,这是别家都没有的关键资产)。
- 挖什么: `trafilatura/core.py`/`main_extractor` 的正文抽取启发式;metadata 提取(标题/日期/站点);姊妹仓 adbar/htmldate 的日期启发式(抄成 stdlib 纯函数的首选);CLI 的输出格式约定(TXT/MD/JSON)作为 fetcher 中间产物格式参考。
- SKIP 什么: 爬虫/sitemap/feed 遍历部分(那是 L1 recall 的事,且我们取证是定向 URL);GPL 时代(<1.8.0)的任何代码。
- 坑: 依赖 lxml(C 扩展),与 stdlib-only 冲突,引入需创始人批准;单作者维护,长期 bus factor 风险;对 JS 渲染页(部分 SPA 定价页)无能为力——那类页面走 CLAUDE.md 已预留的 vps_browser/CCHandoffBackend 路径,不是 trafilatura 的锅。
- recommendation: concepts-borrow(现在);live fetcher 获批时升级为 adopt-as-dependency 候选
- 理由: 合规低频取证不需要浏览器与反爬军备,一个纯 Python 抽取器 + stdlib urllib 就够,且 htmldate 的日期提取直接喂 24 个月红线。
- 与硬约束的冲突: lxml 依赖与 stdlib-only 冲突 → 裁剪:近期先抄日期/正文启发式为纯函数,live 票获批时再作为单个轻依赖申请;离线默认无冲突(live 本来就是 opt-in)。

## 评估过但不推荐(skip 清单,防重爬)

- firecrawl(github.com/firecrawl/firecrawl)— skip:核心 AGPL-3.0 + 云功能分层(自托管阉割),典型云绑定;其 /extract"schema 进、结构化出"的接口概念已被 crawl4ai prompts 覆盖,不碰代码。
- open-deep-research(github.com/langchain-ai/open_deep_research)— skip:MIT 但深绑 LangGraph 运行时与 LangGraph Platform,supervisor 多 agent 编排对"3 个定向 fetcher"严重过重;prompt 价值与 gpt-researcher 重叠。
- searxng(github.com/searxng/searxng)— skip:AGPL-3.0 且是需常驻自托管服务的元搜索引擎;enrich 是定向取证不需要搜索发散,且撞"不引数据库/服务"非目标。
- scrapegraph-ai(github.com/ScrapeGraphAI/Scrapegraph-ai)— skip:MIT、活跃,但 langchain 系重依赖 + README 重推自家云 API;"自然语言→抽取 graph"模式的可借部分与 crawl4ai LLM extraction 重叠且更绕。
- deep-research(github.com/dzhng/deep-research)— skip(可惜):MIT、<500 行、递归 breadth/depth 循环 + "learnings 抽取" prompt 是全品类最易读的最小实现,但近单作者、2026 年仅零星维护,且其递归发散搜索机制正是我们要砍掉的部分;想读最小范本时看 `src/deep-research.ts` 即可,不登记为源。
- markitdown(github.com/microsoft/markitdown)— skip:MIT/微软/很活跃,但定位是 office 文档→markdown,网页主内容去噪能力弱于 trafilatura,对取证场景不对口。
- auto-deep-research(github.com/HKUDS/Auto-Deep-Research)— skip:绑定自家 AutoAgent 全自动 agent 框架,重运行时,无可单独剥离的取证资产。
- open-deep-research(github.com/nickscamara/open-deep-research)— skip:Firecrawl 官方演示性 Next.js 应用,云 API(Firecrawl/Vercel AI SDK)绑定,无独立机制可挖。

## 本 lane 的搜索方法沉淀

- 最有效入口:直接逐个 WebFetch 种子仓库的 GitHub 首页(拿 stars/license/release 一步到位),再 fetch `raw.githubusercontent.com/.../prompts.py` 读 prompt 原文——**prompt 文件名几乎总叫 `prompts.py` 或在 `src/prompt.ts`**,先猜路径直读比搜代码快。
- `.../commits/main` 页面判断"单作者是否停更"很可靠(dzhng/deep-research 由此定级)。
- 有效检索词:"X alternative"(由 firecrawl 引出 crawl4ai/trafilatura 谱系)、"open deep research clone"(引出 nickscamara/HKUDS 等衍生,基本都是壳,快速排除)。
- 死胡同:找"证据结构化 prompt"的通用检索(如 "web page to structured evidence LLM prompt")全是博客软文;真正的范式都藏在抓取框架的 `prompts.py` 里,应按"框架→prompt 文件"路径挖而非按用例搜。
- 给未来 miner skill:本 lane 的源要钉 commit 挖三个文件级资产——gpt-researcher `gpt_researcher/prompts.py`、crawl4ai `crawl4ai/prompts.py`、adbar/htmldate 的核心启发式;三者更新都快,镜像后 diff 追踪比追 HEAD 稳。
