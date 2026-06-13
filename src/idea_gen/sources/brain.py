"""源② 灵感收件箱：data/raw/inbox.jsonl（每行一个 JSON）。永远离线。

动态化体现在"持续录入"那一端（Studio 的 POST /api/inbox 往这个文件追加），采集侧
只需把当前文件读出来即可。
"""

from __future__ import annotations

from pathlib import Path

from idea_core.models import SOURCE_BRAIN

from . import CollectContext, read_jsonl, register


class BrainInboxAdapter:
    name = "brain"
    source = SOURCE_BRAIN
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        path = Path(ctx.config["path"]) if ctx.config.get("path") else ctx.raw_dir / "inbox.jsonl"
        records = read_jsonl(path)
        for r in records:
            r.setdefault("source", self.source)
            r.setdefault("source_name", "manual")
        return records


register(BrainInboxAdapter())
