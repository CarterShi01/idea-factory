"""⑤enrich fetcher:服务市场成交(有人已经在人肉解决并收钱)。"""

from __future__ import annotations

from idea_factory.contract.models import EVIDENCE_DEAL

from .base import _FixtureFetcher


class DealsFetcher(_FixtureFetcher):
    """Marketplace/service transaction records -- 有人已经在人肉解决并收钱。"""

    kind = EVIDENCE_DEAL
    fixture_name = "deals.jsonl"
