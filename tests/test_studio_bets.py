"""Tests for the read-only machine endpoint GET /api/bets (studio backend).

Same shape as test_studio_top3.py: boots a real ThreadingHTTPServer against a
temp PROCESSED dir and hits it over HTTP. /api/bets serves bet_memos.json
verbatim (agent-service-plan.md §2.2) -- the full hypothesis/evidence/
experiment record, not the one-liner top3() gives.
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
KEY = "test-bets-key"


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_under_test_bets", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


_BET_MEMOS_ENVELOPE = {
    "schema_version": 2, "stage": "bet_memos", "run_id": "run-2026-07-08-1",
    "week": "2026-W28", "date": "2026-07-08", "count": 1,
    "items": [
        {
            "bet_id": "a", "run_id": "run-2026-07-08-1", "title": "Idea A", "verdict": "pursue",
            "hypothesis": {"pain": "p", "solution": "s", "target_user": "u", "why_now": "n", "why_only_me": "m"},
            "evidence": [{"kind": "hiring", "source_url": "https://x.example.com"}],
            "riskiest_assumption": "A risk", "killer_objection": "obj",
            "persona_objections": [], "experiment": {"metric": "signups", "target": 10,
                                                       "kill_below": 3, "horizon_days": 7, "budget_band": "0-500元"},
            "eval_score": 72.0, "confidence": "real", "lineage_url": "/#/run/run-2026-07-08-1/idea/a",
        },
    ],
}


@pytest.fixture
def server(tmp_path, monkeypatch):
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


def test_valid_key_returns_full_bet_memos(server):
    base, _app, processed = server
    (processed / "bet_memos.json").write_text(json.dumps(_BET_MEMOS_ENVELOPE), encoding="utf-8")

    status, data = _get(f"{base}/api/bets", key=KEY)
    assert status == 200
    assert data["run_id"] == "run-2026-07-08-1"
    assert data["week"] == "2026-W28"
    assert data["count"] == 1
    assert len(data["bets"]) == 1
    bet = data["bets"][0]
    assert bet["bet_id"] == "a"
    assert bet["experiment"]["metric"] == "signups"
    assert bet["hypothesis"]["pain"] == "p"
    assert set(data) == {"run_id", "week", "date", "count", "bets"}


def test_missing_key_is_401(server):
    base, _app, processed = server
    (processed / "bet_memos.json").write_text(json.dumps(_BET_MEMOS_ENVELOPE), encoding="utf-8")
    status, _ = _get(f"{base}/api/bets")
    assert status == 401


def test_wrong_key_is_401(server):
    base, _app, processed = server
    (processed / "bet_memos.json").write_text(json.dumps(_BET_MEMOS_ENVELOPE), encoding="utf-8")
    status, _ = _get(f"{base}/api/bets", key="nope")
    assert status == 401


def test_missing_bet_memos_is_empty_200(server):
    base, _app, _processed = server  # no bet_memos.json written
    status, data = _get(f"{base}/api/bets", key=KEY)
    assert status == 200
    assert data["count"] == 0
    assert data["bets"] == []
