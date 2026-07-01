"""Tests for the read-only machine endpoint GET /api/top3 (studio backend).

Loads the stdlib-only studio server, points it at a temp screened.json, boots a
real ThreadingHTTPServer on an ephemeral port, and hits it over HTTP:
  * valid Bearer key  -> 200 + correct top-3 structure (kills excluded, ranked)
  * missing/wrong key -> 401
  * empty/absent screened.json -> 200 with {"count": 0, "top3": []}
"""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "studio" / "server" / "app.py"
KEY = "test-top3-key"


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_under_test", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


_SCREENED = [
    # pre-sorted the way idea_eval writes it: survivors first (by -score), kills last
    {"idea_id": "a", "title": "Idea A", "verdict": "pursue", "eval_score": 72.0,
     "riskiest_assumption": "A risk", "cheap_experiment": "A test", "killed_by": []},
    {"idea_id": "b", "title": "Idea B", "verdict": "review", "eval_score": 55.0,
     "riskiest_assumption": "B risk", "cheap_experiment": "B test", "killed_by": []},
    {"idea_id": "c", "title": "Idea C", "verdict": "review", "eval_score": 50.0,
     "riskiest_assumption": "C risk", "cheap_experiment": "C test", "killed_by": []},
    {"idea_id": "d", "title": "Idea D", "verdict": "review", "eval_score": 48.0,
     "riskiest_assumption": "D risk", "cheap_experiment": "D test", "killed_by": []},
    {"idea_id": "z", "title": "Killed Z", "verdict": "kill", "eval_score": 80.0,
     "riskiest_assumption": "Z risk", "cheap_experiment": "Z test",
     "killed_by": ["pain_real"]},
]


@pytest.fixture
def server(tmp_path, monkeypatch):
    """Boot the studio app against a temp PROCESSED dir. Yields (base_url, app)."""
    app = _load_app()
    processed = tmp_path / "processed"
    processed.mkdir()
    monkeypatch.setattr(app, "PROCESSED", processed)
    monkeypatch.setattr(app, "TOP3_API_KEY", KEY)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", app, processed
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url, key=None):
    req = urllib.request.Request(url)
    if key is not None:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_valid_key_returns_ranked_top3(server):
    base, _app, processed = server
    (processed / "screened.json").write_text(json.dumps(_SCREENED), encoding="utf-8")

    status, data = _get(f"{base}/api/top3", key=KEY)
    assert status == 200
    assert data["count"] == 3
    assert len(data["top3"]) == 3
    # kills excluded, order preserved, ranks assigned 1..3
    assert [r["idea_id"] for r in data["top3"]] == ["a", "b", "c"]
    assert [r["rank"] for r in data["top3"]] == [1, 2, 3]
    assert "z" not in [r["idea_id"] for r in data["top3"]]

    top = data["top3"][0]
    for field in ("rank", "idea_id", "title", "one_liner", "score",
                  "verdict", "riskiest_assumption", "cheap_experiment"):
        assert field in top
    assert top["score"] == 72.0
    assert top["verdict"] == "pursue"
    assert "Idea A" in top["one_liner"]
    # top-level machine schema shape
    assert set(data) == {"date", "generated_at", "count", "top3"}
    assert len(data["date"]) == 10  # YYYY-MM-DD


def test_missing_key_is_401(server):
    base, _app, processed = server
    (processed / "screened.json").write_text(json.dumps(_SCREENED), encoding="utf-8")
    status, _ = _get(f"{base}/api/top3")  # no Authorization header
    assert status == 401


def test_wrong_key_is_401(server):
    base, _app, processed = server
    (processed / "screened.json").write_text(json.dumps(_SCREENED), encoding="utf-8")
    status, _ = _get(f"{base}/api/top3", key="nope")
    assert status == 401


def test_missing_screened_is_empty_200(server):
    base, _app, _processed = server  # no screened.json written
    status, data = _get(f"{base}/api/top3", key=KEY)
    assert status == 200
    assert data["count"] == 0
    assert data["top3"] == []


def test_empty_screened_is_empty_200(server):
    base, _app, processed = server
    (processed / "screened.json").write_text("[]", encoding="utf-8")
    status, data = _get(f"{base}/api/top3", key=KEY)
    assert status == 200
    assert data["count"] == 0
    assert data["top3"] == []
