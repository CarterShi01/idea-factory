"""Tests for token/cost/latency instrumentation (Studio v2 cost-gradient panel).

Verifies: Router captures usage+latency; the offline/mock path leaves usage null;
prices.json drives cost (null when unpriced); trace rows carry usage/cost/latency;
and the default rule path writes no trace at all (offline invariant).
"""

from __future__ import annotations

import json
from datetime import date

import idea_factory.runtime.llm as llm
from idea_factory.runtime import ledger
from idea_factory.runtime.llm import LLMRequest, LLMResponse, MockBackend, RouterBackend, cost_of


class _FakeResp:
    def __init__(self, obj):
        self._b = json.dumps(obj).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_router_captures_usage_and_latency(monkeypatch):
    def fake_urlopen(req, timeout=0):
        return _FakeResp({
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        })
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    b = RouterBackend(base_url="http://x/v1", api_key="k", model="tc-code")
    out = b.complete([LLMRequest(id="i1", system="s", user="u")])
    assert out[0].usage == {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
    assert out[0].latency_ms is not None and out[0].latency_ms >= 0


def test_mock_leaves_usage_null():
    out = MockBackend().complete([LLMRequest(id="i1", system="s", user="u")])
    assert out[0].usage is None
    assert out[0].latency_ms is None


def test_cost_null_when_model_unpriced(monkeypatch, tmp_path):
    monkeypatch.setenv("IDEA_LLM_CONFIG_DIR", str(tmp_path))
    (tmp_path / "prices.json").write_text('{"tc-code": {"input_per_1k": 0.002, "output_per_1k": 0.008}}')
    llm._PRICES_CACHE = None  # reset cache for this dir
    usage = {"prompt_tokens": 1000, "completion_tokens": 1000, "total_tokens": 2000}
    assert cost_of("tc-code", usage) == round(0.002 + 0.008, 6)   # 1k in + 1k out
    assert cost_of("unpriced-model", usage) is None               # unknown model -> null
    assert cost_of("tc-code", None) is None                       # no usage -> null
    llm._PRICES_CACHE = None


def test_trace_row_carries_usage_cost_latency(tmp_path):
    r = LLMResponse(id="i1", text="x", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                    latency_ms=42.0)
    req = LLMRequest(id="i1", system="s", user="u", model="tc-code")
    llm.log_trace_batch(tmp_path, "run-1", "generate", [req], {"i1": r}, "generate@v1")
    rows = ledger.read_trace(tmp_path, "run-1", "generate")
    assert len(rows) == 1
    assert rows[0]["usage"]["total_tokens"] == 15
    assert rows[0]["latency_ms"] == 42.0
    assert "cost" in rows[0]  # null (no prices.json here) but present


def test_log_trace_batch_noop_without_run_id(tmp_path):
    req = LLMRequest(id="i1", system="s", user="u")
    llm.log_trace_batch(tmp_path, None, "generate", [req], {"i1": LLMResponse(id="i1")}, "v")
    assert ledger.read_trace(tmp_path, "none", "generate") == []


def test_default_rule_run_writes_no_trace(tmp_path):
    """Offline invariant: rule generate + no judge backend => zero traces, zero tokens."""
    from idea_factory import pipeline
    import shutil
    from pathlib import Path

    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    for name in ("inbox.jsonl", "personas.json", "sample_signals.json"):
        src = Path("data/raw") / name
        if src.exists():
            shutil.copy2(src, data / "raw" / name)
    if Path("data/raw/fixtures").exists():
        shutil.copytree("data/raw/fixtures", data / "raw" / "fixtures")

    pipeline.run(data_dir=data, output_dir=data / "processed", today=date(2026, 7, 7))
    traces_root = ledger.ledger_dir(data) / "traces"
    # no LLM backend selected => no trace tree written at all
    assert not traces_root.exists() or not any(traces_root.rglob("*.jsonl"))
