"""源①「钱在流动的地方」之一：服务成交信号(自由职业/服务市场)。

有人已经在人肉解决这个痛点并收钱,软件化就是机会(docs/design/pipeline-v2-plan.md
§0/§5①)。离线 demo / 测试用静态 fixture 底座(``data/raw/fixtures/marketplace.jsonl``),
永不触网;``live=True`` 的真实市场页抓取是需要创始人明确批准的后续工作,这里先出接口
占位,直接返回 ``[]``。
"""

from __future__ import annotations

from idea_factory.contract.models import SOURCE_EXTERNAL

from . import CollectContext, read_jsonl, register

_FIXTURE = "fixtures/marketplace.jsonl"


class MarketplaceAdapter:
    name = "marketplace"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.live:
            return []  # 真实服务市场抓取:需创始人批准后再接,见模块 docstring
        records = read_jsonl(ctx.raw_dir / _FIXTURE)
        for r in records:
            r.setdefault("source", self.source)
        return records


register(MarketplaceAdapter())
