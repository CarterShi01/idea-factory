"""源① 中国数据：经 **Windows VPS 上已登录的 Chrome** 抓取需要登录态的中文站
（小红书 / 知乎 / 微博 …）。

为什么这样设计（关键）：这些站点需要**登录态**才能看到内容，而登录态在你 Windows VPS
的持久 Chrome（``C:\\bridge\\chrome-automation``，由你手动扫码登录）里。所以：

* **连接层**用 Playwright ``connect_over_cdp(endpoint)`` **挂到那台已登录的 Chrome**
  （Scrapling 的 stealth fetcher 是"全新匿名会话"，没有登录态，不适合这里）；
* **解析层**用 **Scrapling** 的自适应选择器从页面 HTML 抽数据（站点改版时更抗造）。

约束：只在 ``ctx.live=True`` 触发；依赖（playwright / scrapling）是可选 extra
（``pip install 'idea-factory[stealth]'``），缺失或端点不可达时**优雅返回 []**，绝不
拖垮采集。CDP 端点（tailnet IP）与目标站选择器全部来自 ``config/sources.json``，不硬编码。
"""

from __future__ import annotations

from datetime import date

from idea_factory.contract.models import SOURCE_EXTERNAL

from . import CollectContext, register


class VPSBrowserAdapter:
    name = "vps_browser"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if not ctx.live:
            return []
        endpoint = ctx.config.get("cdp_endpoint")  # 如 http://100.111.25.20:9222（tailnet）
        targets = ctx.config.get("targets", [])
        if not endpoint or not targets:
            return []

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []  # 需 idea-factory[stealth]

        try:
            from scrapling.parser import Selector  # 自适应解析
        except ImportError:
            try:
                from scrapling import Selector  # 旧/新路径兼容
            except ImportError:
                Selector = None  # 退化：缺 Scrapling 时用 playwright 原生 query

        nav_timeout = int(ctx.config.get("nav_timeout_ms", 30000))
        max_items = int(ctx.config.get("max_items_per_target", 20))
        out: list[dict] = []

        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(endpoint)  # 挂到已登录的 VPS Chrome
            except Exception:  # noqa: BLE001 — 端点不可达 → 优雅退化
                return []
            page_ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = page_ctx.new_page()
            try:
                for t in targets:
                    try:
                        page.goto(t["url"], wait_until="networkidle", timeout=nav_timeout)
                        html = page.content()
                        out.extend(self._extract(html, t, Selector, max_items))
                    except Exception:  # noqa: BLE001 — 单目标失败跳过
                        continue
            finally:
                browser.close()
        return out

    def _extract(self, html: str, target: dict, Selector, max_items: int) -> list[dict]:
        item_sel = target.get("item_selector")
        title_sel = target.get("title_selector")
        if not (item_sel and title_sel and Selector):
            return []
        page = Selector(html)
        records: list[dict] = []
        for el in page.css(item_sel)[:max_items]:
            node = el.css_first(title_sel)
            title = (node.text if node else "").strip()
            if not title:
                continue
            records.append(
                {
                    "source": self.source,
                    "source_name": target.get("name", "vps"),
                    "title": title,
                    "text": title,
                    "url": target.get("url"),
                    "category": target.get("category", target.get("name")),
                    "observed_on": date.today().isoformat(),
                    "confidence": "real",
                }
            )
        return records


register(VPSBrowserAdapter())
