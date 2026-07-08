"""Tests for POST /api/outcome (studio backend) -- the inbound boundary
artifact (agent-service-plan.md §2.3): oc pushes a bet's real-world result;
idea-factory only receives + records, idempotent on event_id.
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
KEY = "test-outcome-key"


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_under_test_outcome", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


@pytest.fixture
def server(tmp_path, monkeypatch):
    app = _load_app()
    data_dir = tmp_path / "data"
    processed = data_dir / "processed"
    processed.mkdir(parents=True)
    monkeypatch.setattr(app, "DATA_DIR", data_dir)
    monkeypatch.setattr(app, "PROCESSED", processed)
    monkeypatch.setattr(app, "TOP3_API_KEY", KEY)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", app, data_dir, processed
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(url, body, key=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if key is not None:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


_BODY = {
    "event_id": "oc-card-1234-final", "candidate_id": "a", "tested_at": "2026-07-20",
    "metric": "signups", "actual": 4, "reported_by": "oc",
}


def test_valid_push_is_recorded(server):
    base, app, data_dir, _processed = server
    status, data = _post(f"{base}/api/outcome", _BODY, key=KEY)
    assert status == 200
    assert data["ok"] is True
    assert data["duplicate"] is False

    from idea_factory.runtime import ledger
    outcomes = ledger.read_outcomes(data_dir)
    assert len(outcomes) == 1
    assert outcomes[0]["candidate_id"] == "a"
    assert outcomes[0]["event_id"] == "oc-card-1234-final"
    assert outcomes[0]["reported_by"] == "oc"
    assert outcomes[0]["actual"] == {"metric": "signups", "value": 4.0}


def test_duplicate_event_id_is_a_noop(server):
    base, _app, data_dir, _processed = server
    _post(f"{base}/api/outcome", _BODY, key=KEY)
    status, data = _post(f"{base}/api/outcome", _BODY, key=KEY)
    assert status == 200
    assert data["duplicate"] is True

    from idea_factory.runtime import ledger
    assert len(ledger.read_outcomes(data_dir)) == 1  # not double-recorded


def test_missing_key_is_401(server):
    base, _app, _data_dir, _processed = server
    status, _ = _post(f"{base}/api/outcome", _BODY)
    assert status == 401


def test_wrong_key_is_401(server):
    base, _app, _data_dir, _processed = server
    status, _ = _post(f"{base}/api/outcome", _BODY, key="nope")
    assert status == 401


def test_missing_required_field_is_400(server):
    base, _app, _data_dir, _processed = server
    body = dict(_BODY)
    del body["metric"]
    status, data = _post(f"{base}/api/outcome", body, key=KEY)
    assert status == 400
    assert "error" in data


def test_target_auto_filled_from_bet_memo_when_omitted(server):
    base, _app, _data_dir, processed = server
    bet_memos = {
        "schema_version": 2, "stage": "bet_memos", "run_id": "run-1",
        "week": "2026-W28", "date": "2026-07-08", "count": 1,
        "items": [{
            "bet_id": "a", "run_id": "run-1", "title": "A", "verdict": "pursue",
            "hypothesis": {}, "evidence": [], "riskiest_assumption": "", "killer_objection": "",
            "persona_objections": [],
            "experiment": {"metric": "signups", "target": 10, "kill_below": 3,
                            "horizon_days": 7, "budget_band": "0-500元"},
            "eval_score": 70.0, "confidence": "real", "lineage_url": "/#/run/run-1/idea/a",
        }],
    }
    (processed / "bet_memos.json").write_text(json.dumps(bet_memos), encoding="utf-8")

    body = dict(_BODY)
    del body["event_id"]  # no idempotency key needed for this check
    status, data = _post(f"{base}/api/outcome", body, key=KEY)
    assert status == 200
    assert data["target_used"] == 10.0
