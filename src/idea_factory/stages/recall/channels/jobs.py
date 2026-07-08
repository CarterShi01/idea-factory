"""源①「钱在流动的地方」之一：招聘信号。

企业愿意为一个痛点付薪招人,是最强的付费证据之一(docs/design/pipeline-v2-plan.md
§0/§5①)。离线 demo / 测试用静态 fixture 底座(``data/raw/fixtures/jobs.jsonl``),永不
触网。``live=True`` 复用 vps_browser 的共享 CDP+Scrapling 机制(agent-service-plan.md
M-C1,创始人 2026-07-08 拍板"live 一律走 vps_browser"——不新写爬虫):挂到已登录的
VPS Chrome,访问 ``config/sources.json`` 本段的 ``targets``(BOSS直聘等招聘站,当前
留空,等创始人给站点清单 + DOM 选择器,见该文档 §5-①)。无 targets 时优雅返回 ``[]``。
"""

from __future__ import annotations

from idea_factory.contract.models import SOURCE_EXTERNAL

from . import CollectContext, read_jsonl, register
from .vps_browser import fetch_via_browser

_FIXTURE = "fixtures/jobs.jsonl"


class JobsAdapter:
    name = "jobs"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.live:
            return fetch_via_browser(ctx.config, source=self.source, source_name_default="jobs")
        records = read_jsonl(ctx.raw_dir / _FIXTURE)
        for r in records:
            r.setdefault("source", self.source)
        return records


register(JobsAdapter())
