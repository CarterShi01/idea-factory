"""源① 实时：Hacker News Algolia 搜索 API（免 key、增量、纯 stdlib）。

只在 ``ctx.live=True`` 时触网；失败返回 ``[]``（单源隔离）。增量：``created_at_i > since``
（since = 现在 - window_days）。
"""

from __future__ import annotations

import time
from datetime import date
from urllib.parse import quote

from idea_factory.contract.models import SOURCE_EXTERNAL

from . import CollectContext, register

_API = "http://hn.algolia.com/api/v1/search_by_date"


class HNAlgoliaAdapter:
    name = "hn_algolia"
    source = SOURCE_EXTERNAL
    needs_llm = False

    def collect(self, ctx: CollectContext) -> list[dict]:
        if not ctx.live:
            return []
        queries = ctx.config.get("queries") or ["ai agent"]
        window_days = int(ctx.config.get("window_days", 7))
        per_query = int(ctx.config.get("hits_per_query", 40))
        since = int(time.time()) - window_days * 86400

        out: list[dict] = []
        for q in queries:
            url = (
                f"{_API}?query={quote(q)}&tags=story"
                f"&numericFilters=created_at_i>{since}&hitsPerPage={per_query}"
            )
            try:
                data = ctx.get_json(url)
            except Exception:  # noqa: BLE001 — single query failure shouldn't kill the source
                continue
            for h in data.get("hits", []):
                title = h.get("title") or h.get("story_title") or ""
                if not title:
                    continue
                created = h.get("created_at_i")
                out.append(
                    {
                        "source": self.source,
                        "source_name": "hn",
                        "title": title,
                        "text": h.get("story_text") or title,
                        "url": f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                        "category": q,
                        "observed_on": date.fromtimestamp(created).isoformat() if created else "",
                        "points": h.get("points", 0),
                    }
                )
        return out


register(HNAlgoliaAdapter())
