"""DifyBackend: registration, graceful no-key failure, and workflow-output parsing.

Pure unit tests — no network (urlopen is monkeypatched). Mirrors the contract in
dify/flows/README.md: POST /workflows/run with inputs {system,user[,schema]},
read End-node output `result`, extract JSON when a schema is present.
"""
import json

import idea_core.llm as llm
from idea_core.llm import DifyBackend, LLMRequest, get_backend


class _FakeResp:
    def __init__(self, body: dict):
        self._b = json.dumps(body).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_dify_registered_in_factory():
    b = get_backend("dify")
    assert isinstance(b, DifyBackend)
    assert b.name == "dify"


def test_dify_no_key_fails_gracefully(monkeypatch):
    monkeypatch.delenv("IDEA_DIFY_API_KEY", raising=False)
    monkeypatch.delenv("IDEA_DIFY_GENERATE_API_KEY", raising=False)
    b = DifyBackend(step="generate")
    out = b.complete([LLMRequest(id="x", system="s", user="u")])
    assert len(out) == 1
    assert out[0].ok is False
    assert "API_KEY" in out[0].error  # actionable: tells you which env var to set


def test_dify_parses_workflow_output(monkeypatch):
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp({"data": {"outputs": {"result": '{"score": 0.9}'}, "status": "succeeded"}})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    b = DifyBackend(step="judge", api_key="test-key")
    out = b.complete([LLMRequest(id="i1", system="sys", user="usr", schema={"type": "object"})])

    assert out[0].ok is True
    assert out[0].text == '{"score": 0.9}'
    assert out[0].data == {"score": 0.9}  # extracted because a schema was supplied
    # request shape matches the flow contract
    assert captured["url"].endswith("/workflows/run")
    assert captured["payload"]["inputs"]["system"] == "sys"
    assert captured["payload"]["inputs"]["user"] == "usr"
    assert captured["payload"]["response_mode"] == "blocking"


def test_dify_output_key_override(monkeypatch):
    monkeypatch.setenv("IDEA_DIFY_OUTPUT_KEY", "answer")

    def fake_urlopen(req, timeout=0):
        return _FakeResp({"data": {"outputs": {"answer": "hello"}}})

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    b = DifyBackend(step="generate", api_key="k")
    out = b.complete([LLMRequest(id="a", system="", user="hi")])
    assert out[0].ok is True
    assert out[0].text == "hello"
