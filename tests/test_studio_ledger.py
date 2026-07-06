"""Tests for the pipeline-v2 Studio endpoints: ledger funnel/verdicts/outcomes/
trace (read-only), founder-label (write), and the scoped what-if judge rerun.
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


def _load_app():
    spec = importlib.util.spec_from_file_location("studio_app_ledger_test", APP_PATH)
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
    monkeypatch.setattr(app, "PASSWORD", "")  # cookie auth disabled (dev)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", app, data_dir, processed
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_funnel_empty_ledger(server):
    base, *_ = server
    status, data = _get(f"{base}/api/ledger/funnel")
    assert status == 200
    assert data["stage_survival"] == {}
    assert data["outcomes"]["count"] == 0


def test_funnel_reflects_ledger_data(server):
    base, app, data_dir, _ = server
    from idea_factory.runtime import ledger

    ledger.log_impressions_bulk(
        data_dir, "gen-1", "2026-W27", "triage_signal",
        survived_ids=["a"], killed={"b": "stale_24m"}, ts="2026-07-05",
    )
    status, data = _get(f"{base}/api/ledger/funnel")
    assert status == 200
    assert data["stage_survival"]["triage_signal"]["survived"] == 1
    assert data["kill_reasons"] == {"stale_24m": 1}


def test_verdicts_and_outcomes_endpoints(server):
    base, app, data_dir, _ = server
    from idea_factory.runtime import ledger

    ledger.log_verdict(data_dir, {"idea_id": "a", "verdict": "pursue"}, actor="system")
    status, data = _get(f"{base}/api/ledger/verdicts")
    assert status == 200 and len(data) == 1

    from idea_factory.stages.retro import outcomes as retro
    retro.record_outcome(data_dir, "a", "2026-07-12", "signups", 7.0, target=10.0)
    status, data = _get(f"{base}/api/ledger/outcomes")
    assert status == 200 and len(data) == 1


def test_trace_endpoint_requires_params_and_reads_back(server):
    base, app, data_dir, _ = server
    from idea_factory.runtime import ledger

    status, data = _get(f"{base}/api/ledger/trace")
    assert status == 400

    ledger.log_trace(
        data_dir, "eval-1", "diligence", "a", prompt_version="judge@v1",
        request={"user": "x"}, response={"verdict": "kill"},
    )
    status, data = _get(f"{base}/api/ledger/trace?run_id=eval-1&stage=diligence")
    assert status == 200
    assert len(data) == 1
    assert data[0]["entity_id"] == "a"


def test_founder_label_writes_and_validates(server):
    base, app, data_dir, _ = server
    status, data = _post(f"{base}/api/ledger/label", {"candidate_id": "a", "action": "star"})
    assert status == 200 and data["ok"] is True

    from idea_factory.runtime import ledger
    records = ledger.read_jsonl(ledger.ledger_dir(data_dir) / ledger.VERDICTS)
    assert len(records) == 1
    assert records[0]["event"] == "founder_star"
    assert records[0]["actor"] == "founder"

    status, data = _post(f"{base}/api/ledger/label", {"candidate_id": "a"})  # missing action
    assert status == 400


_IDEA = {
    "id": "a", "signal_id": "s1", "source": "external_event", "title": "候选A",
    "pain": "痛点", "solution": "方案", "target_user": "开发者", "observed_on": "2026-06-01",
    "confidence": "real",
    "factors": {
        "pain_intensity": 0.7, "payment_signal": 0.7, "build_cost": 0.8,
        "distribution_fit": 0.6, "market_freshness": 0.5, "competition_density": 0.6,
        "moat_signal": 0.5, "founder_fit": 0.6,
    },
    "alpha": 0.5, "decay": 1.0,
}


def test_whatif_judge_rerun_does_not_persist_anything(server):
    base, app, data_dir, processed = server
    (processed / "ideas.json").write_text(json.dumps([_IDEA]), encoding="utf-8")

    status, data = _post(f"{base}/api/run/whatif-judge", {"idea_id": "a", "backend": "mock"})
    assert status == 200
    assert data["idea_id"] == "a"
    assert "verdict" in data

    # nothing written: no screened.json, no ledger directory, ideas.json untouched.
    assert not (processed / "screened.json").exists()
    assert not (data_dir / "ledger").exists()
    assert json.loads((processed / "ideas.json").read_text())[0]["id"] == "a"


def test_whatif_judge_unknown_idea_is_400(server):
    base, app, data_dir, processed = server
    (processed / "ideas.json").write_text(json.dumps([_IDEA]), encoding="utf-8")
    status, data = _post(f"{base}/api/run/whatif-judge", {"idea_id": "does-not-exist"})
    assert status == 400


def test_whatif_judge_rejects_cc_backend(server):
    base, app, data_dir, processed = server
    (processed / "ideas.json").write_text(json.dumps([_IDEA]), encoding="utf-8")
    status, data = _post(f"{base}/api/run/whatif-judge", {"idea_id": "a", "backend": "cc"})
    assert status == 400


def test_whatif_judge_applies_overrides(server):
    base, app, data_dir, processed = server
    (processed / "ideas.json").write_text(json.dumps([_IDEA]), encoding="utf-8")
    status, data = _post(
        f"{base}/api/run/whatif-judge",
        {"idea_id": "a", "backend": "mock", "overrides": {"factors": {**_IDEA["factors"], "pain_intensity": 0.0}}},
    )
    assert status == 200
    # overridden factors flow into evaluate_idea -> lower score than the original.
    assert data["eval_score"] < 50
