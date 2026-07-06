"""⑤enrich fetcher:竞品定价页(有名字有价格的方案)。

live 版(抓真实定价页)是需创始人批准的后续票——接口/夹具已就位,填 fetch 的
live 分支即可(候选路径:vps_browser 挂已登录 Chrome 读公开页,或 CCHandoffBackend)。
"""

from __future__ import annotations

from idea_factory.contract.models import EVIDENCE_COMPETITOR_PRICING

from .base import _FixtureFetcher


class PricingFetcher(_FixtureFetcher):
    """Competitor pricing pages -- 有名字有价格的方案。"""

    kind = EVIDENCE_COMPETITOR_PRICING
    fixture_name = "pricing.jsonl"
