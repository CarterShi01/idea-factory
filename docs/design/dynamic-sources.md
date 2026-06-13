# 三源动态化设计（已落地）

把三个信号源从"读静态文件"升级为**动态**：记住历史、只取增量、感知"变化本身"。本文是已实现版本的设计说明（代码见 `src/idea_gen/sources/`、`src/idea_core/state.py`、`trends.py`、`src/idea_gen/persona/`）。

## 0. 统一原则

"动态" = **有状态 + 增量 + 调度 + 文件交接 + token 纪律**。抓取/去重/趋势全程零 token（cron 可跑）；只有 LLM 步（生成 A / 评委 B / 源③痛点合成）走腾讯 router 或手动 CC（2026-06-15 起禁止程序化调 CC）。离线 demo 默认路径不联网、幂等。

## 1. 统一骨架：适配器 + 共享状态 + 配置驱动

```
src/idea_gen/sources/         适配器层（沿用 idea_core.llm 的 Protocol+注册表范式）
  __init__.py   SourceAdapter 协议 + REGISTRY + CollectContext + 注入式 HTTP
  static_external.py / brain.py / persona.py   离线 fixture（行为不变）
  hn_algolia.py     源① 实时（HN Algolia，免 key，opt-in live）
  vps_browser.py    源① 中国数据（连 Windows VPS 已登录 Chrome + Scrapling，opt-in）
src/idea_core/
  state.py   SeenStore(跨日去重) + SignalHistory(话题×日趋势序列)  → data/state/*.jsonl
  trends.py  Moving Z-Score 突增检测 → rising/steady/peaked + growth_speed
config/sources.json   配置驱动:启停/查询词/RSS/CDP 端点/目标站选择器
data/state/   seen.jsonl + signal_history.jsonl（gitignored，cron 维护，零 token）
```

- **适配器协议**：`collect(ctx) -> list[dict]`；`ctx.live=True` 才触网；单源失败隔离。
- **动态地基**：`collect_all(live=...)`、`run_pipeline(live=..., use_state=...)`。`use_state=True` 时：`SignalHistory` 记录所有信号话题 → `SeenStore` 只放行**新**指纹 → `trends.classify` 回填 `trend_status/growth_speed`。默认 `False` 保持 demo 幂等。
- **趋势回喂因子**：`factors.market_freshness` = 关键词命中 ⊕ 趋势（rising +0.3 / peaked −0.2 + 0.2·growth_speed）；无趋势字段时退化为旧关键词分（纯函数契约不变，gen/evl 不漂移）。
- **CJK 修复**：`normalize`/`dedup` 切分改为 `[a-z0-9]+|[一-鿿]`，中文信号才有区分度的指纹/近重判断。

## 2. 源③：动态全选 + 细分人群（`src/idea_gen/persona/`）

商业内核：**先找痛点才能赚钱** → 不凭空造人群，按价值挑高价值人群 → 在其中找真实痛点。

- **可增长 taxonomy**（`taxonomy.json`，面向中国创业）：种子（独立开发者/内容创作者/小微商家/跨境/独立投资人…）+ 派生（源①真实信号里反复出现的 target_user 自动登记，待接）+ 裂变（LLM 细分，待接）。
- **全选 → 细分挑选**（`select.py`）：`flatten_leaves` 拉平所有叶子人群（不漏）；`segment_priority` = 可变现先验·0.45 + 触达·0.25 + 真实趋势证据·0.30，再 × 久未挖探索奖励；`select_segments` 取 Top-N（控 token/噪声）。
- **四维价值分**（`persona_value`）：可变现性·0.35 + 痛点严重度·0.30 + 触达·0.20 − 竞争·0.15 → 优先能赚钱的人群×痛点。
- **grounded 合成 + 佐证闸门**（`synthesize.py` + `crosscheck.py`）：对选中人群，把源①里相关真实信号作上下文，LLM 批量合成痛点；`corroborate()` 用 CJK token-set Jaccard 在真实信号里找佐证 → 命中标 `synthetic_grounded`（放行）、未命中标 `synthetic_only`（降权）。防 LLM persona 乐观偏差。

## 3. 三源交叉自喂（`crosscheck.py`）

- 源①真实趋势 **佐证** 源③合成痛点（上面的 grounding 闸门，已实现）。
- 源①真实趋势 **加权** 源②脑海 idea（`corroborate` 可复用，pipeline 接入待办）。
- 多源命中 = 可信度更高（`evidence` 字段，待接 idea-eval）。

## 4. Scrapling + Windows VPS 登录态抓取（`vps_browser.py`）

需要登录态的中文站（小红书/知乎/微博）：登录态在你 **Windows VPS 的持久 Chrome**。
- **连接层** = Playwright `connect_over_cdp(endpoint)` 挂到那台已登录 Chrome（tailnet 上的 9222；Scrapling 的 stealth fetcher 是全新匿名会话、没登录态，不适合）。
- **解析层** = **Scrapling** 自适应选择器从页面 HTML 抽数据（站点改版更抗造）。
- opt-in extra（`pip install 'idea-factory[stealth]'`）；缺依赖/端点不可达 → 优雅返回 []。端点与选择器全在 `config/sources.json`。

## 5. 调度与 Studio

- **零 token 步**（采集/去重/趋势/源②录入）→ cron 纯 Python。**LLM 步**（A/B/源③合成）→ 腾讯 router 自动 或 CC 手动文件交接。
- **Studio**：Run 面板新增「实时抓取」「动态状态」开关 + 源③合成后端选择 + 「源② 记一条灵感」录入框（`POST /api/inbox` 追加 `inbox.jsonl`）。

## 6. 分期与开放问题

已落地：地基（state/trends/适配器/配置）、源③人群系统、源③ grounded 合成+佐证、HN/VPS 适配器骨架、Studio 集成。
待接：源①真实抓取 live 冒烟（HN/VPS 需网络/桥）、target_user 自动派生 taxonomy、源②趋势加权接入 pipeline、idea-eval 用 source_diversity/synthetic_only 硬下限。
开放问题：趋势 topic 粒度（关键词 vs 聚类）、SignalHistory 冷启动 warmup、人群裂变防爆炸上限、佐证阈值 τ（同义词漏判）、趋势进 alpha 还是只进 evl（避免双计）。

> 数据源偏好：约 70% 中国源、面向中国创业（黑猫投诉≈中国版 CFPB、知乎/小红书/微博/应用商店评论/大众点评/36氪…）；中国 UGC 反爬重 → 正是 Scrapling 可选层用武之地。详见 docs/research/04、05。
