"""Tests for external signal collection (network injected, never real)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from idea_factory import collect


def _fixed_now() -> str:
    return "2026-05-29T00:00:00+00:00"


def test_fetch_hacker_news_maps_top_stories() -> None:
    stories = {
        collect.HN_TOP_STORIES_URL: [11, 22, 33],
        collect.HN_ITEM_URL.format(item_id=11): {
            "id": 11,
            "title": "Show HN: A new build tool",
            "url": "https://example.com/11",
            "text": "details",
            "time": 1_700_000_000,
        },
        collect.HN_ITEM_URL.format(item_id=22): {
            "id": 22,
            "title": "Ask HN: hiring?",
            "url": "https://example.com/22",
        },
    }

    def fake_get_json(url: str) -> Any:
        return stories.get(url)

    records = collect.fetch_hacker_news(2, get_json=fake_get_json, now=_fixed_now)

    assert [r["id"] for r in records] == ["hn-11", "hn-22"]
    assert all(r["source"] == "hackernews" for r in records)
    assert all(r["collected_at"] == _fixed_now() for r in records)
    assert records[0]["name"] == "Show HN: A new build tool"
    assert records[0]["launched_at"] == "2023-11-14"


def test_fetch_hacker_news_skips_items_without_title() -> None:
    stories = {
        collect.HN_TOP_STORIES_URL: [1, 2],
        collect.HN_ITEM_URL.format(item_id=1): {"id": 1, "title": "Keep me"},
        collect.HN_ITEM_URL.format(item_id=2): None,
    }
    records = collect.fetch_hacker_news(5, get_json=lambda u: stories.get(u), now=_fixed_now)
    assert [r["id"] for r in records] == ["hn-1"]


def test_fetch_product_hunt_without_token_returns_empty(monkeypatch) -> None:
    monkeypatch.delenv(collect.PRODUCT_HUNT_TOKEN_ENV, raising=False)
    monkeypatch.setattr(collect, "_load_dotenv_if_available", lambda: None)

    def boom(*_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover - must not run
        raise AssertionError("network should not be called without a token")

    assert collect.fetch_product_hunt(5, post_json=boom) == []


def test_fetch_product_hunt_with_token_maps_posts() -> None:
    body = {
        "data": {
            "posts": {
                "edges": [
                    {
                        "node": {
                            "id": "p1",
                            "name": "Cooltron",
                            "tagline": "ship faster",
                            "description": "a devtool",
                            "url": "https://ph.example/p1",
                            "topics": {"edges": [{"node": {"name": "Developer Tools"}}]},
                        }
                    }
                ]
            }
        }
    }
    captured: dict[str, Any] = {}

    def fake_post(url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        captured["headers"] = headers
        return body

    records = collect.fetch_product_hunt(3, token="tok", post_json=fake_post, now=_fixed_now)

    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert len(records) == 1
    assert records[0]["id"] == "ph-p1"
    assert records[0]["source"] == "producthunt"
    assert records[0]["categories"] == ["developer tools"]


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>36kr</title>
  <item>
    <title>新创业公司获得融资</title>
    <link>https://36kr.com/p/1</link>
    <description>一家 AI 公司宣布融资</description>
    <pubDate>Thu, 28 May 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second story</title>
    <link>https://36kr.com/p/2</link>
    <description>more</description>
  </item>
</channel></rss>"""


def test_fetch_domestic_news_parses_feed() -> None:
    feeds = {"36kr": "https://36kr.example/feed"}
    records = collect.fetch_domestic_news(
        feeds, limit_per_feed=10, get_text=lambda u: SAMPLE_RSS, now=_fixed_now
    )
    assert len(records) == 2
    assert records[0]["name"] == "新创业公司获得融资"
    assert records[0]["url"] == "https://36kr.com/p/1"
    assert all(r["source"] == "36kr" for r in records)


def test_fetch_domestic_news_respects_limit_per_feed() -> None:
    records = collect.fetch_domestic_news(
        {"36kr": "u"}, limit_per_feed=1, get_text=lambda u: SAMPLE_RSS, now=_fixed_now
    )
    assert len(records) == 1


def test_fetch_domestic_news_skips_failing_feed() -> None:
    def get_text(url: str) -> str:
        if "bad" in url:
            raise RuntimeError("boom")
        return SAMPLE_RSS

    feeds = {"bad": "https://bad.example/feed", "36kr": "https://36kr.example/feed"}
    records = collect.fetch_domestic_news(feeds, get_text=get_text, now=_fixed_now)
    assert records and all(r["source"] == "36kr" for r in records)


def test_collect_all_combines_sources_and_isolates_failures() -> None:
    hn = {
        collect.HN_TOP_STORIES_URL: [1],
        collect.HN_ITEM_URL.format(item_id=1): {"id": 1, "title": "HN one"},
    }

    def get_text(url: str) -> str:
        raise RuntimeError("rss down")  # this source fails, others must survive

    records = collect.collect_all(
        hn_limit=5,
        ph_limit=0,
        get_json=lambda u: hn.get(u),
        get_text=get_text,
        now=_fixed_now,
    )
    assert [r["id"] for r in records] == ["hn-1"]


def test_save_collected_round_trips(tmp_path: Path) -> None:
    records = [{"id": "hn-1", "name": "中文", "source": "hackernews"}]
    out = tmp_path / "nested" / "collected.json"
    returned = collect.save_collected(records, out)
    assert returned == out
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == records
    assert "中文" in out.read_text(encoding="utf-8")  # ensure_ascii=False


def test_run_scheduled_runs_bounded_iterations() -> None:
    calls: list[int] = []
    slept: list[float] = []
    collect.run_scheduled(
        lambda: calls.append(1),
        interval_seconds=10,
        iterations=3,
        sleep=slept.append,
    )
    assert len(calls) == 3
    # run_immediately fires once before the first sleep, so 2 sleeps for 3 runs.
    assert slept == [10, 10]


def test_run_scheduled_without_immediate_run_sleeps_first() -> None:
    order: list[str] = []
    collect.run_scheduled(
        lambda: order.append("job"),
        interval_seconds=5,
        run_immediately=False,
        iterations=1,
        sleep=lambda s: order.append("sleep"),
    )
    assert order == ["sleep", "job"]
