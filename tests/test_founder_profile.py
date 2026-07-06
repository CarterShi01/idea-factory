"""Tests for the editable founder-profile endpoints (studio backend).

Boots the stdlib-only studio server against a temp config/founder.json on an
ephemeral port and drives it over HTTP:
  * GET  /api/founder-profile      -> 200 + the kernel-read keys are present
  * PUT  /api/founder-profile      -> 200, file rewritten, factors can read it
  * PUT with reach_keywords_en missing -> 400 AND the original file is untouched
"""

from __future__ import annotations

import importlib.util
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "studio" / "server" / "app.py"

_VALID = {
    "_version": "v1",
    "_labels": {"identity": "身份定位"},
    "identity": "一人公司创始人:全栈 + 产品",
    "capital_rmb": 60000,
    "capital_note": "启动资金约 6 万人民币",
    "skills": ["10 年软件工程", "10 年产品经理"],
    "network": ["认识安全/云厂商销售"],
    "language_region_edge": ["蒙语母语优势"],
    "reach_keywords_en": ["developer", "saas", "mongolian"],
    "reach_keywords_zh": ["开发者", "蒙语", "内蒙古"],
    "hard_constraints": ["一人 2 周-2 月可做出 MVP"],
    "anti_fit": ["纯投放冷启动 to-C"],
}


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_founder_test", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Boot the studio app pointed at a temp founder.json. Yields (base_url, app, path)."""
    app = _load_app()
    founder = tmp_path / "founder.json"
    founder.write_text(json.dumps(_VALID, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(app, "FOUNDER_PATH", founder)
    monkeypatch.setattr(app, "PASSWORD", "")  # cookie auth disabled (dev), same gate as prod

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", app, founder
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _put(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


REQUIRED_KEYS = (
    "identity",
    "capital_rmb",
    "skills",
    "network",
    "language_region_edge",
    "reach_keywords_en",
    "reach_keywords_zh",
    "hard_constraints",
    "anti_fit",
)


def test_get_returns_required_keys(server):
    base, _app, _path = server
    status, data = _get(f"{base}/api/founder-profile")
    assert status == 200
    for key in REQUIRED_KEYS:
        assert key in data, f"missing kernel-read key: {key}"
    assert isinstance(data["reach_keywords_en"], list)
    assert isinstance(data["identity"], str)
    # metadata rides through untouched
    assert data.get("_version") == "v1"


def test_put_valid_writes_and_factors_can_read(server, monkeypatch):
    base, _app, path = server
    payload = {**_VALID, "reach_keywords_en": ["developer", "fintech", "b2b"]}
    status, data = _put(f"{base}/api/founder-profile", payload)
    assert status == 200
    assert data.get("ok") is True

    # File was rewritten with the new value.
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["reach_keywords_en"] == ["developer", "fintech", "b2b"]

    # factors._load_founder_reach reads config/founder.json via IDEA_FOUNDER_PROFILE;
    # point it at the file we just wrote and confirm the new keyword folds in.
    monkeypatch.setenv("IDEA_FOUNDER_PROFILE", str(path))
    import idea_factory.factors as factors

    reach = factors._load_founder_reach()
    assert "fintech" in reach
    assert "开发者" in reach or "developer" in reach


def test_put_missing_reach_keywords_is_400_and_preserves_file(server):
    base, _app, path = server
    before = path.read_text(encoding="utf-8")

    bad = {k: v for k, v in _VALID.items() if k != "reach_keywords_en"}
    status, data = _put(f"{base}/api/founder-profile", bad)
    assert status == 400
    assert "reach_keywords_en" in data.get("error", "")

    # Original file is byte-for-byte untouched (atomic write never happened).
    assert path.read_text(encoding="utf-8") == before


def test_put_bad_identity_type_is_400(server):
    base, _app, path = server
    before = path.read_text(encoding="utf-8")
    bad = {**_VALID, "identity": 123}
    status, data = _put(f"{base}/api/founder-profile", bad)
    assert status == 400
    assert "identity" in data.get("error", "")
    assert path.read_text(encoding="utf-8") == before
