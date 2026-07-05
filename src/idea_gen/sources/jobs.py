"""源①「钱在流动的地方」之一：招聘信号。

企业愿意为一个痛点付薪招人,是最强的付费证据之一(docs/design/pipeline-v2-plan.md
§0/§5①)。离线 demo / 测试用静态 fixture 底座(``data/raw/fixtures/jobs.jsonl``),永不
触网;``live=True`` 的真实招聘网站抓取是需要创始人明确批准的后续工作(CLAUDE.md:
不经批准不得给默认管线加真实外部 API 调用),这里先出接口占位,直接返回 ``[]``。
"""

from __future__ import annotations

from idea_core.models import SOURCE_EXTERNAL

from . import CollectContext, read_jsonl, register

_FIXTURE = "fixtures/jobs.jsonl"


class JobsAdapter:
    name = "jobs"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.live:
            return []  # 真实招聘网站抓取:需创始人批准后再接,见模块 docstring
        records = read_jsonl(ctx.raw_dir / _FIXTURE)
        for r in records:
            r.setdefault("source", self.source)
        return records


register(JobsAdapter())
