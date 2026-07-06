from datetime import date

from idea_factory.runtime.llm import LLMResponse, MockBackend
from idea_factory.stages.recall.persona.crosscheck import corroborate
from idea_factory.stages.recall.persona import load_taxonomy, select_segments
from idea_factory.stages.recall.persona.synthesize import synthesize_pains


def test_corroborate_matches_real_signal():
    real = [{"title": "独立 SaaS 创始人手动对账 Stripe 很痛苦", "trend_status": "rising"}]
    c = corroborate("独立 SaaS 创始人对账繁琐", real)
    assert c.real_hits >= 1
    assert c.trend == "rising"
    # unrelated pain -> no corroboration
    assert corroborate("农民灌溉调度困难", real).real_hits == 0


def test_synthesize_grounds_and_flags():
    segs = select_segments(load_taxonomy(), n=2)
    real = [{"title": "独立 SaaS 客服 工单 重复", "category": "saas"}]

    def responder(req):
        return LLMResponse(id=req.id, data={"pains": [
            {"summary": "独立 SaaS 客服重复工单耗时", "verbatim": "天天回一样的问题", "severity": 0.8},
            {"summary": "完全无关的边缘问题 xyz", "verbatim": "..."},
        ]})

    out = synthesize_pains(segs, real, MockBackend(responder), {"user_template": "{persona} {signals}"})
    assert out, "expected synthesized pains"
    conf = {p["confidence"] for p in out}
    assert "synthetic_grounded" in conf   # 被真实信号佐证的
    assert all(p["source"] == "pain_persona" for p in out)


def test_pipeline_persona_backend_mock(tmp_path):
    def responder(req):
        return LLMResponse(id=req.id, data={"pains": [{"summary": f"痛点-{req.id}", "verbatim": "x"}]})

    # inject persona LLM via collect_all path by using mock backend name + monkeypatch-free:
    from idea_factory.stages.recall import collect
    raw = collect.collect_all("data", persona_llm=MockBackend(responder))
    persona = [r for r in raw if r.get("source") == "pain_persona"]
    assert persona and all(r["source_name"] == "persona_llm" for r in persona)
