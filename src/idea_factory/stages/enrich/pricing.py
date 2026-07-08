"""⑤enrich fetcher:竞品定价页(有名字有价格的方案)。

live 版(抓真实定价页)机制已拍板(vps_browser 挂已登录 Chrome,CC-handoff 已否决,
见 base.py 模块 docstring "M-C2"),但 evidence 的结构化提取(keywords/source_date/
numbers)仍需站点清单 + 真实页面结构才能不猜测地接线,故仍是 stub。
"""

from __future__ import annotations

from idea_factory.contract.models import EVIDENCE_COMPETITOR_PRICING

from .base import _FixtureFetcher


class PricingFetcher(_FixtureFetcher):
    """Competitor pricing pages -- 有名字有价格的方案。"""

    kind = EVIDENCE_COMPETITOR_PRICING
    fixture_name = "pricing.jsonl"
