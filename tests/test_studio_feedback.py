"""Tests for POST/GET /api/feedback (studio backend) -- rich founder feedback
(problem-locating labels + free-text note) with a FROZEN lineage snapshot.

Drives a real offline `idea run` into a temp data dir (same pattern as
test_studio_runs.py), then posts feedback on one surviving idea and asserts the
record lands in feedback.jsonl self-contained (labels + note + a frozen lineage
that carries signal/candidate/diligence), and that GET filters to that idea.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import threading
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "studio" / "server" / "app.py"


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_feedback_test", APP_PATH)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


@pytest.fixture
def server(tmp_path, monkeypatch):
    from idea_factory import pipeline

    app = _load_app()
    data_dir = tmp_path / "data"
    processed = data_dir / "processed"
    raw = data_dir / "raw"
    raw.mkdir(parents=True)
    for name in ("inbox.jsonl", "personas.json", "sample_signals.json"):
        src = REPO_ROOT / "data" / "raw" / name
        if src.exists():
            shutil.copy2(src, raw / name)
    fx = REPO_ROOT / "data" / "raw" / "fixtures"
    if fx.exists():
        shutil.copytree(fx, raw / "fixtures")

    pipeline.run(data_dir=data_dir, output_dir=processed, today=date(2026, 7, 7),
                 judge_backend="mock")

    monkeypatch.setattr(app, "DATA_DIR", data_dir)
    monkeypatch.setattr(app, "PROCESSED", processed)
    monkeypatch.setattr(app, "PASSWORD", "")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", app, data_dir, processed
    finally:
        httpd.shutdown()
        httpd.server_close()


def _first_idea(base):
    _, runs = _get(f"{base}/api/runs")
    rid = runs[0]["run_id"]
    _, dd = _get(f"{base}/api/run/{rid}/stage/diligence")
    idea = dd["items"][0]
    return rid, idea["id"]


def test_feedback_records_labels_note_and_frozen_lineage(server):
    base, _app, data_dir, _proc = server
    rid, idea_id = _first_idea(base)

    status, resp = _post(f"{base}/api/feedback", {
        "run_id": rid, "idea_id": idea_id,
        "labels": ["wrong_kill", "weak_evidence"],
        "note": "证据其实挺牵强的，judge 不该这么快 kill",
    })
    assert status == 200 and resp["ok"] is True
    assert resp["feedback_id"]

    from idea_factory.runtime import ledger
    rows = ledger.read_feedback(data_dir)
    assert len(rows) == 1
    r = rows[0]
    assert r["run_id"] == rid and r["idea_id"] == idea_id
    assert r["labels"] == ["wrong_kill", "weak_evidence"]
    assert "牵强" in r["note"]
    # the frozen, self-contained lineage snapshot
    lin = r["lineage"]
    assert lin["candidate"] is not None
    assert lin["signal"] is not None
    assert "diligence" in lin
    assert r["lineage_url"] == f"/#/run/{rid}/idea/{idea_id}"


def test_feedback_note_only_is_allowed(server):
    base, _app, data_dir, _proc = server
    rid, idea_id = _first_idea(base)
    status, _ = _post(f"{base}/api/feedback", {
        "run_id": rid, "idea_id": idea_id, "labels": [], "note": "只写一段话，不选标签",
    })
    assert status == 200
    from idea_factory.runtime import ledger
    assert len(ledger.read_feedback(data_dir)) == 1


def test_feedback_empty_is_400(server):
    base, _app, _data_dir, _proc = server
    rid, idea_id = _first_idea(base)
    status, data = _post(f"{base}/api/feedback", {
        "run_id": rid, "idea_id": idea_id, "labels": [], "note": "",
    })
    assert status == 400
    assert "error" in data


def test_feedback_requires_ids(server):
    base, *_ = server
    status, _ = _post(f"{base}/api/feedback", {"labels": ["wrong_kill"]})
    assert status == 400


def test_get_feedback_filters_to_idea(server):
    base, _app, _data_dir, _proc = server
    rid, idea_id = _first_idea(base)
    _post(f"{base}/api/feedback", {"run_id": rid, "idea_id": idea_id,
                                   "labels": ["good_catch"], "note": ""})

    status, rows = _get(f"{base}/api/feedback?run_id={rid}&idea_id={idea_id}")
    assert status == 200
    assert len(rows) == 1
    # compact row (no heavy frozen lineage in the list view)
    assert "lineage" not in rows[0]
    assert rows[0]["labels"] == ["good_catch"]

    # a different idea id sees nothing
    _, empty = _get(f"{base}/api/feedback?run_id={rid}&idea_id=nonexistent")
    assert empty == []
