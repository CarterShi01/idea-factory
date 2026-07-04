# 中文源(源①·vps_browser)上线 runbook

> 目标:把小红书/知乎的**真实**中文信号接进源①,替换当前的罐头假数据,喂给源③那些
> 多样目标用户(英语学习者/情绪压力/老人数字鸿沟/慢病/蒙语)。代码(`src/idea_gen/sources/vps_browser.py`)
> 和配置(`config/sources.json` 的 `vps_browser`)都已就绪并**武装**(`enabled:true`),
> 只差下面这些**基建/运维**步骤——这些必须在能触达那台已登录 Chrome 的机器上做。

## 为什么现在还没真跑(卡点)

- 那台**已登录**小红书/知乎的 Chrome 在 Windows VPS(tailnet `100.111.25.20:9222`)。
- idea-gen 实际运行的核心机(claude-user 沙箱)**没有 tailnet**,也没桥到 VPS:9222。
  本地 `127.0.0.1:9222` 是另一个**全新无登录态**的无头 Chrome,抓中文站只会撞登录墙。
- 现有 socat 桥只有 `8931`(playwright-mcp)/`8951`(win-mcp),**都不是**裸 CDP,
  `connect_over_cdp` 用不了。

## 上线步骤(devops / 在能触达登录 Chrome 的机器)

1. **打通到登录 Chrome 的裸 CDP**(二选一,均属改运行栈=7 硬门,创始人/devops 执行):
   - (a) 加一条 socat 桥,仿现有 browser 桥:`local 172.17.0.1:9222 → VPS 100.111.25.20:9222`,
     然后把 `config/sources.json` 的 `cdp_endpoint` 改成桥地址(如 `http://172.17.0.1:9222`)。
   - (b) 直接在 VPS 上跑 idea-gen(那里 `localhost:9222` 就是登录 Chrome),但 `.env`/Dify 配置需一并带过去。
2. **确认 VPS Chrome 已登录**小红书 + 知乎(手动扫码,持久 profile `C:\bridge\chrome-automation`)。
3. **装可选依赖**(在运行机):`pip install -e '.[stealth]' && playwright install chromium`
   (当前核心机 `scrapling` 未装)。
4. **调选择器**:`config/sources.json` 里 `item_selector`/`title_selector` 是猜的,
   首次几乎必改——对着实时页面 DOM 调(小红书/知乎会改版)。先小跑 `max_items_per_target` 保守值。
5. **真跑**:`PYTHONPATH=src python3 -m idea_gen --gen-backend dify --live --top-n 15`
   (`--live` 是触网闸;不带则源①静默、走离线)。核对产出里 `source_name=zhihu_*/xhs_*` 的真实条目。

## 已对齐的部分(无需再动)

- 搜索词已从"独立开发/创业痛点"(创始人镜像)改为**目标用户痛点**:英语口语/背单词、
  焦虑失眠、老人智能手机、慢病复诊用药、内蒙蒙语。真实信号落进对应 `category`,
  经 `derive.py` 还会自动把反复出现的 `target_user` 登记成新人群(源③自动挖人群那条腿)。
- `enabled:true` 已武装;`--live` 缺省时离线默认路径完全不受影响(已验证)。
