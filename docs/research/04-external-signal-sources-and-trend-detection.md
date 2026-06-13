# 外部信号采集源与趋势检测

> 调研范围：盘点高价值"外部事件变化"信号源与开源采集/趋势检测工具，评估免费 API/RSS 可用性与抓取合规性，给出"趋势上升期"检测方法，并输出可立即接入 `idea-factory/collect.py` 的优先级清单。

idea-factory 当前的 `collect.py` 已经做对了几件关键事：所有 HTTP 走可注入的 `get_json / get_text / post_json`（便于离线测试与替换后端）、每条记录统一映射到 normalize 消费的 record 形状、网络只在显式 `collect` 时发生。本报告的所有建议都以"延续这套适配器模式、不破坏离线 demo 契约"为前提。

## 一、信号源全景与免费可用性

把信号源按"获取成本/合规风险"分三档。核心结论：**HN Firebase + Algolia、arXiv、GitHub Trending(RSS)、各类 newsletter/RSS 是真正零成本且合规的基本盘；Product Hunt 可用但需 token 且默认禁止商用；Reddit 与 Crunchbase 在 2025 后已基本"付费墙化"，不建议进 demo 主路径。**

| 信号源 | 免费 API / RSS | 鉴权 | 速率/配额 | 合规要点 | 推荐度 |
|---|---|---|---|---|---|
| Hacker News (Firebase) | `https://hacker-news.firebaseio.com/v0/`，已接入 | 无 | 官方无文档化限流（读流量基本不限） | 官方开放接口，最稳 | 高（已有）|
| HN Algolia Search | `https://hn.algolia.com/api/v1/` | 无 | 有限流但个人使用免费 | 支持 `search_by_date` + `numericFilters` 按时间窗口计数，做趋势检测的利器 | 高 |
| arXiv API | `http://export.arxiv.org/api/query` (Atom)，另有每日 RSS | 无 | 建议每次调用间隔 3 秒；单次 max_results≤2000，总量≤30000 | 开放，须看 Terms of Use；午夜更新，需缓存 | 高 |
| GitHub Trending | 无官方 API；社区 RSS 生成器 (GitHubTrendingRSS) | 无 | 取决于 RSS 源 | 官方 trending 页面无 API，靠非官方 RSS 较稳 | 中高 |
| Product Hunt | GraphQL `v2/api/graphql`，已接入 | OAuth token | 6250 复杂度点/15min；其余端点 450 请求/15min | **默认禁止商用**，商用需邮件申请 hello@producthunt.com | 中（已有，注意合规）|
| 国内资讯 (36kr/虎嗅 RSS) | RSS，已接入 | 无 | 取决于源 | RSS 公开输出 | 中（已有）|
| Google Trends | 无稳定官方库；官方 API 2025 上线但 alpha、配额受限 | 视方案 | alpha 配额小 | pytrends 已于 2025-04-17 归档只读；爬取属灰色 | 中（谨慎）|
| Exploding Topics | 无免费 API（SaaS/Semrush 旗下） | 付费 | — | 商业产品，只能作"方法论参考"或人工灵感源 | 低（方法论参考）|
| Reddit | 官方 API | OAuth + 预审批 | 免费档 100 req/min（OAuth）/10 req/min（匿名） | 2025 Responsible Builder Policy：**任何访问都需预审批**，商用 $0.24/1k 请求且需谈判 | 低（合规成本高）|
| Crunchbase | **2025 起免费档已取消** | 付费 | Basic $49/mo 起，API 需 Pro $99/mo | 融资数据需付费 | 低（用免费替代）|
| 融资/招聘替代源 | Growjo（招聘速度，免费）、Dealroom、VC Beast（免费 VC 数据） | 视源 | — | Growjo 以招聘速度作为增长代理，免费 | 中（替代 Crunchbase）|

### 关键合规/可用性变化（2025–2026）
- **pytrends 已死**：2025-04-17 归档，仓库只读，频繁随 Google 内部端点变动失效，不适合生产。替代：`trendspyg`（活跃维护的开源后继）、`pytrends-modern`（2025-12 发布的社区 fork，加了重试/async，但仍是非官方 wrapper、同样受限）、或 Google 官方 alpha API。
- **Reddit**：2025 新政要求所有 app（含个人项目）预审批，审核 2–4 周且不保证通过。不建议作为 demo 默认源。
- **Crunchbase**：免费 API 时代结束。融资信号建议改用 **Growjo（免费招聘增长代理）+ Dealroom + VC Beast** 组合，或退化为人工录入。
- **Product Hunt**：技术可用，但默认条款禁止商用——idea-factory 若走向商业化需提前邮件申请，当前 demo 阶段保持"opt-in 且不商用"即可。

## 二、"趋势上升期"检测方法

信号源解决"有什么在发生"，趋势检测解决"什么正在加速"。idea-factory 的价值点正是后者——不是抓最热（最热往往已过早期窗口），而是抓**早期加速**。

### 推荐：滑动窗口计数 + Moving Z-Score（零依赖、可进 stdlib）
这是与本项目"stdlib 优先、不加重依赖"原则最契合的方案：

1. **构造时间序列**：对某个关键词/话题/topic，用 HN Algolia 的 `search_by_date` + `numericFilters=created_at_i>...` 按周（或日）滚动窗口计数命中数量。社区实践证明"按时间窗口对同一查询计数"对追踪技术热度异常有效。
2. **Moving Z-Score 突增检测**：维护滑动窗口的移动均值与标准差，当新点偏离均值超过 `threshold` 个标准差即触发"上升信号"。三个参数：`lag`（窗口长度，决定稳定性 vs 响应速度）、`threshold`（触发 z 分数）、`influence`（新信号对均值/方差的影响，0–1）。其优点是"信号本身不污染阈值"，鲁棒、纯标准库可实现、适合实时监控。
3. **可选增强：STL 分解去季节性**（`statsmodels`）——把序列拆成 趋势/季节/残差，对残差做异常检测，避免"周一发布潮""会议季"造成的伪上升。仅在确有季节性时再引入该依赖。

### Exploding Topics 的方法论可借鉴点
它本质是"多平台信号聚合 + ML 识别早期加速 + 人工确认"，并把趋势分为 Exploding / Regular / Peaked，再加 Speed、Seasonality 维度。idea-factory 可以用更轻的方式复刻这个**状态机**：给每个话题打 `rising / steady / peaked` 标签，并附 `growth_speed` 与 `seasonality` 两个标量——这比单纯"热度排序"更能定位早期窗口。

### 更重的可选项（暂不建议进 demo）
`tsmoothie`、`dtaianomaly`、`TimeGPT`（Nixtla）等是更完整的异常检测工具，但都属于"重依赖/外部模型"，与离线 demo 契约冲突，列为远期可选。

## 三、对 idea-factory / idea-evl 的具体借鉴 / 可落地建议

### 给 idea-factory（采集层）

**优先级清单（按"价值/接入成本"排序）：**

| 优先级 | 动作 | 说明 |
|---|---|---|
| P0 | 新增 `fetch_hn_algolia(query, since)` 适配器 | 复用现有 `get_json` 注入点，打 `https://hn.algolia.com/api/v1/search_by_date?query=...&numericFilters=created_at_i>...`，为趋势检测提供"按窗口计数"原料。零鉴权、零成本。 |
| P0 | 新增 `fetch_arxiv(query)` 适配器 | 用 `export.arxiv.org/api/query` Atom 输出，复用现有 `parse_rss` 思路（Atom 与 RSS 接近，需小改 namespace）。**务必内置 3 秒间隔 + 本地缓存**（午夜更新）。覆盖"技术/研究前沿"信号源，对软件创业 idea 极相关。 |
| P1 | 新增 GitHub Trending 源（经非官方 RSS） | 无官方 API，接 `GitHubTrendingRSS` 这类社区 RSS，沿用 `fetch_domestic_news` 的 RSS 路径即可，几乎零新代码。 |
| P1 | 新增 `trends.py`：Moving Z-Score 突增检测（纯 stdlib） | 输入"话题→时间序列计数"，输出 `rising/steady/peaked + z_score`。不加任何依赖，符合项目规范。可作为 normalize 之后、generate 之前的一个新 stage，给候选打"时机分"。 |
| P2 | Newsletter / 通用 RSS 源做成配置驱动 | 把 `DEFAULT_DOMESTIC_FEEDS` 升级为可扩展的 feed 注册表（含英文 newsletter、Indie Hackers、arXiv 子领域），数据驱动新增源，无需改代码。 |
| P2 | Google Trends 用 `trendspyg`（可选依赖、降级返回空） | 仿照 Product Hunt token 的"无配置则优雅降级返回 `[]`"模式：未安装/失败就跳过，绝不阻断其他源。明确标注 pytrends 已归档、本源不稳定。 |
| 退出 | Reddit / Crunchbase **暂不进 demo 主路径** | 合规成本（预审批/付费墙）高，与离线 demo 哲学冲突。融资信号改用 Growjo 等免费替代，且只作 opt-in。 |

**工程建议：**
- 统一给 record 增加 `signal_strength` / `trend_status`（rising/steady/peaked）字段，让趋势检测结果顺着现有 record 流转到 generate/rank，不破坏数据形状契约。
- `collect_all` 已做"单源失败隔离"，新增源直接 append 到 `sources` 列表即可，风格一致。
- 所有新源继续走 `get_json/get_text` 注入点，保证测试不触网（与现有 `tests/test_collect_cli.py` 一致）。

### 给 idea-evl（评估层）
- **时机分（timing score）应成为一个独立评估维度**：采集层算出的 `trend_status + z_score` 直接喂给 idea-evl 作为打分输入之一——"靠谱 idea"很大程度是"对的时机"。建议 idea-evl 的评分 schema 预留 `market_timing`、`signal_recency`、`source_diversity`（被几个独立源同时命中）三个维度。
- **多源交叉验证**：同一 idea 若被 HN + arXiv + GitHub Trending 多源独立命中，可信度显著高于单源；这与 Exploding Topics"跨平台信号聚合再人工确认"的方法论一致，可作为 idea-evl 的去噪/加权规则。
- **复刻"趋势状态机"**：把 rising/steady/peaked 作为筛选闸门——idea-evl 可优先放行 rising、对 peaked 降权（避免追已过窗口期的热点），从而帮助系统稳定产出"早期窗口"的候选。

## 四、面向"每天 10~20 条靠谱 idea"的落地建议
1. **采集广度**：HN(Firebase+Algolia) + arXiv + GitHub Trending + 精选 newsletter/RSS 这一组合，零成本零合规风险，足以支撑日更体量。
2. **趋势收窄**：用 Moving Z-Score 从每日上百条原始信号里筛出"正在加速"的 20–40 个话题。
3. **交叉去噪 + 时机打分**：交给 idea-evl，按 source_diversity 与 market_timing 加权，输出最终 10–20 条。
4. **合规底线**：商业化前不要把 Product Hunt 数据用于商用、不要把 Reddit/Crunchbase 拉进默认路径。

## 参考链接
- Hacker News 抓取（Firebase/Algolia 端点与时间窗口计数）: https://dev.to/agenthustler/how-to-scrape-hacker-news-in-2026-stories-comments-ask-hn-via-api-21fb
- Hacker News API 指南（Algolia + Firebase）: https://cotera.co/articles/hacker-news-api-guide
- Hacker News RSS（hnrss.org 等）: https://dupple.com/blog/hacker-news-rss
- arXiv API User Manual（端点/3 秒间隔/配额）: https://info.arxiv.org/help/api/user-manual.html
- arXiv RSS Feeds: https://info.arxiv.org/help/rss.html
- GitHub Trending 非官方 RSS 生成器: https://github.com/mshibanami/GitHubTrendingRSS
- arXiv ML/AI 每日 RSS（非官方）: https://github.com/ml-feeds/arxiv-daily-ml-feed
- Product Hunt API 文档: https://api.producthunt.com/v2/docs
- Product Hunt API 速率限制: https://api.producthunt.com/v2/docs/rate_limits/headers
- Product Hunt 抓取与商用限制（2026）: https://roundproxies.com/blog/scrape-product-hunt/
- Reddit API 定价 2025: https://sellbery.com/blog/how-much-does-the-reddit-api-cost-in-2025/
- Reddit 2025 预审批新政: https://replydaddy.com/blog/reddit-api-pre-approval-2025-personal-projects-crackdown
- Crunchbase API 免费档取消（2026）: https://dev.to/agenthustler/crunchbase-api-in-2026-free-tier-gone-what-startup-data-hunters-do-now-1177
- Crunchbase 替代品（Growjo/Dealroom/VC Beast 等）: https://multilogin.com/blog/best-crunchbase-alternatives-in-2025/
- pytrends 替代品对比（Glimpse）: https://meetglimpse.com/software-guides/pytrends-alternatives/
- trendspyg（pytrends 后继，开源）: https://github.com/flack0x/trendspyg
- pytrends-modern（社区 fork）: https://pypi.org/project/pytrends-modern/0.1.0/
- Best Google Trends Scraping APIs 2026: https://www.scrapingbee.com/blog/best-google-trends-api/
- Exploding Topics 工作原理与方法论: https://www.semrush.com/kb/1490-exploding-topics
- Exploding Topics 使用指南（2025）: https://www.magicslides.app/blog/exploding-topics-how-to-use
- Moving Z-Score vs Moving IQR 异常检测: https://medium.com/@kis.andras.nandor/detecting-time-series-anomalies-moving-z-score-vs-moving-iqr-70754d853105
- 简单实用的时间序列异常检测方法: https://medium.com/bukalapak-data/time-series-anomaly-detection-simple-yet-powerful-approaches-4449ffe1ca12
- dtaianomaly 时间序列异常检测库: https://arxiv.org/pdf/2502.14381
- 时间序列异常检测实用工具集（statsmodels/STL 等）: https://towardsdatascience.com/a-practical-toolkit-for-time-series-anomaly-detection-using-python/
