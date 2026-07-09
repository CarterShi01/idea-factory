"""⑤enrich fetcher:竞品定价页(有名字有价格的方案)。

live 仍是桩。重新评估(2026-07-08)后的结论:C2 不是"缺站点清单"的填空题——
它需要 per-candidate 动态检索(不同于 recall 的固定 targets)+ C3 的 LLM 结构化
(证据门 keys on numbers/source_date,搜索结果页给不了),两者其实是一件事。
详见 base.py 模块 docstring "M-C2" 与 agent-service-plan.md §5-①的设计岔口。
"""

from __future__ import annotations

from idea_factory.contract.models import EVIDENCE_COMPETITOR_PRICING

from .base import _FixtureFetcher


class PricingFetcher(_FixtureFetcher):
    """Competitor pricing pages -- 有名字有价格的方案。"""

    kind = EVIDENCE_COMPETITOR_PRICING
    fixture_name = "pricing.jsonl"
