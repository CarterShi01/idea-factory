"""源①「钱在流动的地方」之一：竞品差评信号(1-3 星评论)。

已付费用户的不满,是最便宜的需求验证(docs/design/pipeline-v2-plan.md §0/§5①)。
离线 demo / 测试用静态 fixture 底座(``data/raw/fixtures/reviews.jsonl``),永不触网;
``live=True`` 的真实评论页抓取是需要创始人明确批准的后续工作,这里先出接口占位,
直接返回 ``[]``。
"""

from __future__ import annotations

from idea_core.models import SOURCE_EXTERNAL

from . import CollectContext, read_jsonl, register

_FIXTURE = "fixtures/reviews.jsonl"


class ReviewsAdapter:
    name = "reviews"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.live:
            return []  # 真实评论页抓取:需创始人批准后再接,见模块 docstring
        records = read_jsonl(ctx.raw_dir / _FIXTURE)
        for r in records:
            r.setdefault("source", self.source)
        return records


register(ReviewsAdapter())
