---
doc: research
lane: L1
title: "recall:信号采集"
date: 2026-07-06
agent: subagent
---

# L1 recall:信号采集

## 结论速览

Top 3:**media-crawler**(中文社区采集 + "CDP 挂已登录浏览器"合规抓取范式的最佳答案,但 NC license 只能借概念)、**jobspy**(MIT,招聘信号的 per-site scraper 结构 + JobPost schema 可直接 promote 成我们的 jobs fixture 字段)、**changedetection-io**(Apache-2.0,增量监测/价格变化检测的机制全集)。另加一个数据面补充 **google-play-scraper**(MIT 零依赖,竞品差评抓取最贴合 stdlib 铁律)。

最重要的发现:本 lane 问的"挂已登录浏览器只读公开页"合规模式,业界成熟答案就是 MediaCrawler 的 **CDP 模式**(连接用户自己已登录的 Chrome,保留登录态,不做 JS 逆向)——这个模式本身是架构概念,不依赖它的代码,可以在未来 live adapter 里用任何实现复刻;而且它与我们 sources 层"零 token、注入式 HTTP"的约定天然兼容(抓取层不碰 LLM,无成本梯度冲突)。

## 推荐候选(Top 3 + 1 个数据面补充,按价值排序)

### media-crawler
- repository: github.com/NanmiCoder/MediaCrawler
- stars: ~55.5k · license: **自定义"Non-Commercial Learning License 1.1"(非商用!非 SPDX)** · 活跃度: 活跃,多平台持续维护,有 WebUI 等新功能演进
- mined_for:
  - 数据面: 无(license 禁止抄任何代码/文本资产)
  - 机制面: ① CDP 模式——连接用户已登录的本地 Chrome(Chrome DevTools Protocol),保留登录态只读公开页,避开 JS 逆向,这正是我们 live 中文源 adapter 的合规抓取蓝本;② `media_platform/` 每平台一目录的抽象 crawler 结构(与我们 sources registry 同构,验证了现有设计);③ 平台清单 = 中文信号源靶点清单:小红书/抖音/快手/B站/微博/贴吧/知乎
- 挖什么: 只读 README + `docs/` 的 CDP 模式说明与配置项语义(ENABLE_CDP_MODE 类开关)、各平台登录态维护策略(二维码/cookie/浏览器上下文三选一)的**设计描述**;`media_platform/` 目录划分方式(每平台 client/core/field 拆分)作为我们未来 `sources/xiaohongshu.py` 等 adapter 的结构参照
- SKIP 什么: 全部代码文本(NC license 不可抄);MySQL/SQLite/WebUI 存储层(我们 fixture+jsonl 即真相);大规模抓取相关能力(license 与合规双重禁止)
- 坑: license 是自定义非商用条款,idea-factory 是商业探索项目——**任何一行代码都不能进仓**,只能读设计;Playwright 重依赖,"只挖不跑"没问题但绝不能 vendor;平台反爬规则变化快,它的具体选择器/接口时效性差,挖"模式"不挖"参数"
- recommendation: concepts-borrow
- 理由: 中文社区(小红书/知乎)采集 + 合规登录态抓取模式的事实标准,概念价值最高但法律上只能借概念
- 与硬约束的冲突: license 非商用 → 强制降为 concepts-borrow;Playwright 与 stdlib 铁律冲突 → 未来 live 实现用"CDP 概念 + 创始人批准的最小依赖或手动导出"方式裁剪;成本梯度无冲突(纯抓取零 LLM)

### jobspy
- repository: github.com/speedyapply/JobSpy
- stars: ~3.8k · license: MIT · 活跃度: 活跃(最近 commit 2026-02,LinkedIn 解析修复;多贡献者,2025 内新增 Naukri/Bayt 站点)
- mined_for:
  - 数据面: `jobspy/model.py` 的 JobPost schema(title/company/location/job_url/description/job_type/salary min-max-currency-interval/date_posted)→ 可直接 promote 成我们 `data/raw/fixtures/jobs.jsonl` 的字段规范,尤其 salary 三元组是"公司为痛点付薪"强度的量化字段
  - 机制面: per-site scraper 目录结构(`jobspy/{indeed,linkedin,glassdoor,google,ziprecruiter,bayt,naukri,bdjobs}/` + 顶层 `model.py`/`util.py`/`exception.py`)与我们 sources registry 完全同构;各站点抓取难度先验(Indeed 无限速最稳、LinkedIn 约 10 页即限速)是未来 live JobsAdapter 的选站依据
- 挖什么: `jobspy/model.py`(schema 全量字段)、`jobspy/indeed/`(最稳站点的请求构造,MIT 可抄成 stdlib urllib 纯函数)、`jobspy/util.py` 的 salary/date 归一化纯函数、README 的站点限速经验表
- SKIP 什么: LinkedIn/Glassdoor 等强反爬站点的绕过逻辑(合规灰区且极易失效);Poetry 打包与并发抓取壳(我们低频取证不需要)
- 坑: 缺中国站点(无 BOSS直聘/拉勾)——中文招聘信号仍需自建 adapter,它只提供结构范式;各站点解析器随页面改版脆弱,钉 commit 挖 schema 比追 HEAD 更稳;近一次正式 release 是 2025-03,主干比 release 新
- recommendation: adopt
- 理由: MIT + 结构同构 + schema 即拿即用,是 jobs.jsonl fixture 字段设计和未来 live JobsAdapter 的最短路径
- 与硬约束的冲突: 依赖 requests/pandas 等 → 不引依赖,把单站点请求构造抄成 stdlib urllib 纯函数(sources 层已有注入式 `get_json`/`get_text` 接口);离线契约无冲突(live 本来就是 opt-in);成本梯度无冲突
### changedetection-io
- repository: github.com/dgtlmoon/changedetection.io
- stars: ~32.2k · license: Apache-2.0 · 活跃度: 非常活跃(0.55.7 release 2026-05,215 个 release,长期单核心作者但社区大)
- mined_for:
  - 数据面: 无(它是应用不是数据集)
  - 机制面: ① 增量监测的完整机制分解:抓取 → CSS/XPath/JSONPath/jq 过滤到"关心的区域" → 文本 diff → trigger 条件(出现文本/正则/阈值)才算"变化"——这正是我们 recall 侧"竞品定价页变了、招聘数变了才产生 Signal"的事件化范式;② restock/价格检测专用 processor(价格涨跌百分比阈值触发)对标我们的 marketplace/竞品定价监测;③ 快照+diff 而非全量重抓,天然增量、省成本
- 挖什么: `changedetectionio/html_tools.py`(CSS/XPath 内容提取纯函数,Apache 可抄)、`changedetectionio/diff/`(文本 diff 与变化判定)、`changedetectionio/processors/`(text_json_diff 与 restock 两类 processor 的判定逻辑:什么样的 delta 才值得触发)、watch 配置的数据结构(URL+过滤器+触发条件三元组,可映射成我们 `config/sources.json` 的监测项 schema)
- SKIP 什么: Flask Web UI、Apprise 通知栈、Playwright/Chrome fetcher 集群(全是运行时重量,我们只要判定逻辑);调度器(我们按需手动/低频跑)
- 坑: 它是"跑起来才有价值"的服务型应用,直接用与 glue-only 冲突——只挖 diff/filter/trigger 三段纯逻辑;html_tools 依赖 lxml/inscriptis,抄的时候要降级成 stdlib(html.parser + difflib)重写,借算法不借实现细节
- recommendation: concepts-borrow
- 理由: "增量监测有什么可借"这问题的最完整答案,Apache license 下判定逻辑可自由改写成 stdlib 版
- 与硬约束的冲突: 重服务运行时 vs glue-only → 只借三段判定逻辑;lxml 等依赖 vs stdlib → 用 difflib/html.parser 重写;成本梯度无冲突(全程零 LLM,且"变化才产信号"反而帮漏斗省钱)

### google-play-scraper(数据面补充:竞品差评)
- repository: github.com/JoMingyu/google-play-scraper
- stars: ~1k · license: MIT · 活跃度: **停更中(末次 commit 2024-06,单维护者,未归档)**——但目标接口稳定、库自身零依赖,风险可控
- mined_for:
  - 数据面: reviews 输出字段(reviewId/userName/content/**score**/thumbsUpCount/appVersion/at/replyContent)→ 直接 promote 成我们 `reviews.py` adapter 的 fixture 字段;score 字段天然支持"只取 1–3 星"的差评筛选
  - 机制面: 纯 Python 零外部依赖实现(自带 HTTP 与解析),是全部候选里唯一与 stdlib 铁律零距离的实现;分页 continuation token 模式(每页上限 200 条)可照抄
- 挖什么: `google_play_scraper/features/reviews.py`(请求构造 + continuation 分页 + 字段解析,MIT 可整函数抄)、reviews_all 的翻页终止条件、`app()` 的元数据字段(安装量/评分分布 = 竞品体量证据)
- SKIP 什么: search/permissions 等与差评挖掘无关的 feature;不要依赖其长期维护(停更,Google 改版需自己修)
- 坑: 2024-06 起停更,Google Play 内部接口(batchexecute 类)一旦改版无人修——钉 commit 抄函数、自担维护;只覆盖 Google Play,iOS 侧 facundoolano/app-store-scraper 已不维护(见 skip 清单),App Store 差评需另起(iTunes RSS 官方接口可作替代);对中国市场:Google Play 不在大陆,差评信号主要反映海外/出海产品
- recommendation: adopt
- 理由: MIT + 零依赖 + 字段即 fixture,是"竞品 1–3 星差评"信号最省事的落地件,停更风险用钉 commit 对冲
- 与硬约束的冲突: 无(零依赖可直接抄成 stdlib 纯函数;live 抓取仍走 opt-in 批准流程)

## 评估过但不推荐(skip 清单,防重爬)

- rsshub(github.com/DIYgod/RSSHub)— skip:**AGPL-3.0** + 45k 行级 TypeScript 服务运行时,代码一行不能碰;但其 `lib/routes/` 的中文源路由清单(知乎/微博/豆瓣/B站…)可当**站点靶点目录**免费查阅——登记为"目录参考"而非代码源
- facundoolano-google-play-scraper(github.com/facundoolano/google-play-scraper)— skip:JS 生态且作者自述不再主动维护,Python 侧 JoMingyu 版覆盖同一能力
- facundoolano-app-store-scraper(github.com/facundoolano/app-store-scraper)— skip:同作者同状态,iOS 评论用 iTunes 官方 RSS 端点自写更稳
- ossinsight(github.com/pingcap/ossinsight)— skip:Apache 但绑定 TiDB 数据仓库整套栈,"跑起来才有价值";GH 趋势信号直接消费 GHArchive 小时归档或 GitHub/HN 官方 API 更轻(我们已有 hn_algolia adapter)
- gharchive(gharchive.org)— 记录:它是**数据服务**不是可挖代码仓;未来 GH 趋势 adapter 直接 HTTP 拉小时归档即可,无需登记任何分析仓
- bosszp / bosszhipin-spider 家族(github.com/jhcoco/bosszp 等约 10 个同类仓)— skip:清一色一次性课程/毕设项目,Selenium+cookie 硬编码,普遍停更 2 年以上且 BOSS 反爬迭代快,无一值得钉 commit;BOSS直聘信号走"MediaCrawler 式 CDP 挂登录浏览器"自建
- jobclaw(github.com/slothsheepking/jobclaw)— skip:AI 自动投简历 agent,与"招聘=付费证据"的只读信号采集目标错位,且自动申请行为合规风险高
- mohammedcha-gplay-scraper(github.com/Mohammedcha/gplay-scraper)— skip:65+ 字段营销向新仓,权威性与历史不如 JoMingyu 版,无增量价值

## 本 lane 的搜索方法沉淀

- **最有效入口**:直接 fetch 种子仓的 GitHub 首页 + `/commits/main` 判活跃度 + raw LICENSE 文件核实条款——license 必须读原文,MediaCrawler 首页只写"学习研究用途",真实条款(自定义 NC 1.1)在 LICENSE 里才看得全。
- **有效检索词**:`github <平台名> 爬虫 scraper 2025 maintained`(中文平台加中文关键词召回好);`google-play-scraper maintained python`(带"maintained"能把 fork 海里的活仓捞上来);repo 内 `/tree/main/<pkg>` 页面直接看 per-site 目录结构,比读 README 快。
- **死胡同**:检索"BOSS直聘 爬虫"只捞到毕设级项目,中文招聘站没有 JobSpy 级别的维护仓——这是生态空白,自建 adapter 是唯一路径;"合规抓取 已登录浏览器"作为检索词几乎无结果,该模式要用 "CDP mode" / "browser context login state" 才能命中(MediaCrawler README 是这个概念最好的中文表述)。
- **给未来 miner skill 的提示**:本 lane 的仓大多是"反爬对抗型",HEAD 会频繁 breaking——注册 sources.yaml 时钉 commit 比其它 lane 更重要;优先挖 schema/字段定义(改版不影响)而非选择器/端点参数(必过期)。
