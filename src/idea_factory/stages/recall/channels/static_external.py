"""源① 离线 fixture：从 data/raw/sample_signals.json 读外部事件信号。

live 真实抓取由其它源①适配器（hn_algolia / vps_browser …）负责；本适配器是离线
demo / 测试用的静态底座，永远不触网。
"""

from __future__ import annotations

from idea_factory.contract.models import SOURCE_EXTERNAL

from . import CollectContext, read_json, register


class StaticExternalAdapter:
    name = "static_external"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        records = read_json(ctx.raw_dir / "sample_signals.json")
        for r in records:
            r.setdefault("source", self.source)
        return records


register(StaticExternalAdapter())
