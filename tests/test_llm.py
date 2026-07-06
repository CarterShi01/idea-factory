import json

import pytest

from idea_factory.runtime.llm import (
    CCHandoffBackend,
    LLMRequest,
    LLMResponse,
    MockBackend,
    PendingHandoff,
    build_request,
    extract_json,
    get_backend,
    load_step_config,
)


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('here you go: {"a": 1} done') == {"a": 1}
    assert extract_json("no json here") is None
    assert extract_json("") is None


def test_mock_backend_default_and_responder():
    reqs = [LLMRequest(id="1", system="s", user="u")]
    assert MockBackend().complete(reqs)[0].ok

    def responder(r):
        return LLMResponse(id=r.id, text="ok", data={"v": r.user})

    out = MockBackend(responder).complete(reqs)
    assert out[0].data == {"v": "u"}


def test_request_response_roundtrip():
    r = LLMRequest(id="x", system="s", user="u", schema={"type": "object"}, temperature=0.3)
    assert LLMRequest.from_dict(r.to_dict()) == r
    resp = LLMResponse(id="x", text="t", data={"k": 1})
    assert LLMResponse.from_dict(resp.to_dict()) == resp


def test_cc_handoff_writes_pack_then_resumes(tmp_path):
    reqs = [LLMRequest(id="a", system="s", user="ua"), LLMRequest(id="b", system="s", user="ub")]
    backend = CCHandoffBackend(job_dir=tmp_path, job_name="judge-test")

    # First pass: writes a self-contained request pack and stops.
    with pytest.raises(PendingHandoff) as excinfo:
        backend.complete(reqs)
    assert excinfo.value.count == 2
    assert backend.request_path.exists()
    lines = backend.request_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == "a"

    # Human/CC fills the response pack...
    with backend.response_path.open("w") as fh:
        fh.write(json.dumps({"id": "a", "text": "ra", "data": {"verdict": "kill"}}) + "\n")
        fh.write(json.dumps({"id": "b", "text": "rb", "data": {"verdict": "pursue"}}) + "\n")

    # Second pass: reads them back, matched by id.
    out = backend.complete(reqs)
    assert [r.id for r in out] == ["a", "b"]
    assert out[1].data["verdict"] == "pursue"


def test_cc_handoff_marks_missing_responses(tmp_path):
    reqs = [LLMRequest(id="a", system="s", user="u")]
    backend = CCHandoffBackend(job_dir=tmp_path, job_name="j")
    backend.response_path.parent.mkdir(parents=True, exist_ok=True)
    backend.response_path.write_text("")  # empty response pack
    out = backend.complete(reqs)
    assert not out[0].ok
    assert "missing" in out[0].error


def test_get_backend_factory(tmp_path):
    assert get_backend("mock").name == "mock"
    assert get_backend("router").name == "router"
    assert get_backend("cc", job_dir=tmp_path).name == "cc"
    with pytest.raises(ValueError):
        get_backend("nope")


def test_load_real_configs_and_build_request():
    cfg = load_step_config("judge")
    assert cfg["step"] == "judge"
    assert "schema" in cfg
    req = build_request("idea-1", "rendered user prompt", cfg)
    assert req.id == "idea-1"
    assert req.schema == cfg["schema"]
    assert req.temperature == cfg["temperature"]
