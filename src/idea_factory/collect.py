"""External signal collection — Hacker News, Product Hunt, and domestic RSS.

This module is **opt-in and network-using**. It is intentionally NOT part of
the offline demo pipeline (``pipeline.run``): the default ``idea-factory`` run
stays fully offline. Network requests happen only when a user explicitly runs
``idea-factory collect``.

Every collected item is mapped onto the same record shape that
:mod:`idea_factory.normalize` consumes, plus a ``source`` field recording its
origin (its 灵感来源 / inspiration source) and a ``collected_at`` timestamp.

All HTTP access goes through small injectable callables (``get_json`` /
``get_text`` / ``post_json``) so the suite can exercise the adapters without
touching the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

DEFAULT_DATA_DIR = Path("data/raw")
DEFAULT_COLLECTED_PATH = DEFAULT_DATA_DIR / "collected.json"

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"

PRODUCT_HUNT_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
PRODUCT_HUNT_TOKEN_ENV = "PRODUCT_HUNT_TOKEN"
_PRODUCT_HUNT_QUERY = (
    "query($first:Int!){posts(order:VOTES,first:$first){edges{node{"
    "id name tagline description url topics{edges{node{name}}}}}}}"
)

DEFAULT_DOMESTIC_FEEDS: dict[str, str] = {
    "36kr": "https://www.36kr.com/feed",
    "huxiu": "https://www.huxiu.com/rss/0.xml",
}

HTTP_TIMEOUT_SECONDS = 10
SECONDS_PER_DAY = 24 * 60 * 60

# Injection points used by the test suite to avoid real network calls.
JsonGetter = Callable[[str], Any]
TextGetter = Callable[[str], str]
JsonPoster = Callable[[str, dict[str, Any], dict[str, str]], Any]
Clock = Callable[[], str]


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _default_get_json(url: str) -> Any:
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _default_get_text(url: str) -> str:
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def _default_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
    response = requests.post(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _stable_id(prefix: str, seed: str) -> str:
    """Return a deterministic ``<prefix>-<8 hex>`` id for an item lacking one."""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def _blank_record(source: str, collected_at: str) -> dict[str, Any]:
    """Return a unified record skeleton shared across every source adapter."""
    return {
        "id": "",
        "name": "",
        "tagline": "",
        "description": "",
        "url": "",
        "categories": [],
        "target_users": [],
        "pain_points": [],
        "launched_at": "",
        "source": source,
        "collected_at": collected_at,
    }


def _hn_record(story: dict[str, Any], collected_at: str) -> dict[str, Any]:
    record = _blank_record("hackernews", collected_at)
    item_id = story.get("id")
    record["id"] = f"hn-{item_id}" if item_id is not None else _stable_id("hn", str(story))
    record["name"] = str(story.get("title") or "").strip()
    record["url"] = str(story.get("url") or "").strip()
    record["description"] = str(story.get("text") or "").strip()
    posted = story.get("time")
    if isinstance(posted, (int, float)):
        record["launched_at"] = datetime.fromtimestamp(posted, tz=timezone.utc).date().isoformat()
    return record


def fetch_hacker_news(
    limit: int = 10,
    *,
    get_json: JsonGetter = _default_get_json,
    now: Clock = _now_iso,
) -> list[dict[str, Any]]:
    """Fetch the top ``limit`` Hacker News stories as unified records."""
    if limit <= 0:
        return []
    story_ids = get_json(HN_TOP_STORIES_URL) or []
    collected_at = now()
    records: list[dict[str, Any]] = []
    for item_id in story_ids[:limit]:
        story = get_json(HN_ITEM_URL.format(item_id=item_id))
        if not isinstance(story, dict) or not story.get("title"):
            continue
        records.append(_hn_record(story, collected_at))
    return records


def _ph_record(node: dict[str, Any], collected_at: str) -> dict[str, Any]:
    record = _blank_record("producthunt", collected_at)
    node_id = node.get("id")
    record["id"] = f"ph-{node_id}" if node_id is not None else _stable_id("ph", str(node))
    record["name"] = str(node.get("name") or "").strip()
    record["tagline"] = str(node.get("tagline") or "").strip()
    record["description"] = str(node.get("description") or "").strip()
    record["url"] = str(node.get("url") or "").strip()
    topics = node.get("topics", {})
    edges = topics.get("edges", []) if isinstance(topics, dict) else []
    categories: list[str] = []
    for edge in edges:
        name = (edge.get("node", {}) or {}).get("name") if isinstance(edge, dict) else None
        if name:
            categories.append(str(name).strip().lower())
    record["categories"] = categories
    return record


def fetch_product_hunt(
    limit: int = 10,
    *,
    token: str | None = None,
    post_json: JsonPoster = _default_post_json,
    now: Clock = _now_iso,
) -> list[dict[str, Any]]:
    """Fetch the most-upvoted Product Hunt posts as unified records.

    Product Hunt's API requires an OAuth token. Supply one via the ``token``
    argument or the ``PRODUCT_HUNT_TOKEN`` environment variable (a local
    ``.env`` is honoured). When no token is available the adapter degrades
    gracefully and returns an empty list rather than raising, so an unconfigured
    environment can still collect the other sources.
    """
    if limit <= 0:
        return []
    if token is None:
        _load_dotenv_if_available()
        token = os.environ.get(PRODUCT_HUNT_TOKEN_ENV)
    if not token:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"query": _PRODUCT_HUNT_QUERY, "variables": {"first": limit}}
    body = post_json(PRODUCT_HUNT_GRAPHQL_URL, payload, headers)
    edges = (((body or {}).get("data") or {}).get("posts") or {}).get("edges") or []
    collected_at = now()
    records: list[dict[str, Any]] = []
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        if isinstance(node, dict) and node.get("name"):
            records.append(_ph_record(node, collected_at))
    return records


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def parse_rss(xml_text: str, source: str, limit: int, collected_at: str) -> list[dict[str, Any]]:
    """Parse an RSS/Atom feed body into unified records tagged with ``source``."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    records: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = _text(item.find("title"))
        if not title:
            continue
        link = _text(item.find("link"))
        record = _blank_record(source, collected_at)
        record["id"] = _stable_id(source, link or title)
        record["name"] = title
        record["tagline"] = _text(item.find("description"))
        record["description"] = _text(item.find("description"))
        record["url"] = link
        record["launched_at"] = _text(item.find("pubDate"))
        records.append(record)
        if len(records) >= limit:
            break
    return records


def fetch_domestic_news(
    feeds: dict[str, str] | None = None,
    limit_per_feed: int = 10,
    *,
    get_text: TextGetter = _default_get_text,
    now: Clock = _now_iso,
) -> list[dict[str, Any]]:
    """Fetch domestic startup-news RSS feeds (36kr / 虎嗅) as unified records.

    A feed that fails to fetch or parse is skipped; the other feeds still
    contribute their items.
    """
    if feeds is None:
        feeds = DEFAULT_DOMESTIC_FEEDS
    collected_at = now()
    records: list[dict[str, Any]] = []
    for source, url in feeds.items():
        try:
            xml_text = get_text(url)
        except Exception:
            continue
        records.extend(parse_rss(xml_text, source, limit_per_feed, collected_at))
    return records


def collect_all(
    *,
    hn_limit: int = 10,
    ph_limit: int = 10,
    feeds: dict[str, str] | None = None,
    feed_limit: int = 10,
    get_json: JsonGetter = _default_get_json,
    get_text: TextGetter = _default_get_text,
    post_json: JsonPoster = _default_post_json,
    now: Clock = _now_iso,
) -> list[dict[str, Any]]:
    """Collect records from every source, isolating per-source failures.

    A source that raises is skipped so a single flaky endpoint never aborts the
    whole run. Returns the combined list of unified records.
    """
    records: list[dict[str, Any]] = []
    sources: list[Callable[[], list[dict[str, Any]]]] = [
        lambda: fetch_hacker_news(hn_limit, get_json=get_json, now=now),
        lambda: fetch_product_hunt(ph_limit, post_json=post_json, now=now),
        lambda: fetch_domestic_news(feeds, feed_limit, get_text=get_text, now=now),
    ]
    for fetch in sources:
        try:
            records.extend(fetch())
        except Exception:
            continue
    return records


def save_collected(
    records: list[dict[str, Any]],
    path: Path = DEFAULT_COLLECTED_PATH,
) -> Path:
    """Write collected records to ``path`` as UTF-8 JSON and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def run_scheduled(
    job: Callable[[], None],
    *,
    interval_seconds: int = SECONDS_PER_DAY,
    run_immediately: bool = True,
    iterations: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run ``job`` on a fixed interval (default: once per day).

    A deliberately small standard-library scheduler — no extra dependency and
    no daemon framework, in line with the project's offline, stdlib-first
    conventions. ``iterations`` bounds the loop (the suite passes a finite
    value); ``None`` loops until interrupted. ``sleep`` is injectable so tests
    do not wait in real time. Returns the number of times ``job`` ran.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    runs = 0
    if run_immediately:
        job()
        runs += 1
        if iterations is not None and runs >= iterations:
            return runs
    while iterations is None or runs < iterations:
        sleep(interval_seconds)
        job()
        runs += 1
    return runs


def _load_dotenv_if_available() -> None:
    """Best-effort load of a local ``.env`` (python-dotenv is a project dep)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()
