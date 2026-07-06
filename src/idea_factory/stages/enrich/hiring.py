"""⑤enrich fetcher:招聘信号(公司愿意为这个痛点付薪 = 最强付费证据之一)。"""

from __future__ import annotations

from idea_factory.contract.models import EVIDENCE_HIRING

from .base import _FixtureFetcher


class HiringFetcher(_FixtureFetcher):
    """Relevant job postings -- 公司愿意为这个痛点付薪,最强付费证据之一。"""

    kind = EVIDENCE_HIRING
    fixture_name = "hiring.jsonl"
