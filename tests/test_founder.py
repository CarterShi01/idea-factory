"""Founder-profile injection tests.

The founder profile (config/founder.json) describes *who actually builds & sells*
the idea (10y dev+PM, 6万 capital, security/cloud + 中东硬件 + 医生 network, 蒙语/
内蒙古 edge). It must be injected into every LLM step's system prompt and folded
into the distribution_fit reach vocab. All offline.
"""

import json

from idea_core.llm import (
    build_request,
    load_founder_profile,
    render_founder_block,
)


def test_profile_loads_from_repo():
    p = load_founder_profile()
    assert p is not None
    assert p["capital_rmb"] == 60000
    assert any("蒙语" in s for s in p["language_region_edge"])


def test_render_block_mentions_key_constraints():
    block = render_founder_block(load_founder_profile())
    for needle in ["6", "蒙语", "安全", "中东", "医生", "产品经理"]:
        assert needle in block, needle


def test_render_block_empty_for_no_profile():
    assert render_founder_block(None) == ""


def test_build_request_prepends_founder_block():
    cfg = {"system": "ORIGINAL-SYSTEM", "user_template": "{x}"}
    req = build_request("i1", "user text", cfg)
    # ⑤ (dify-prompt-authoring.md §3.2): the founder block now rides in the USER
    # message (data); system stays the pure strategy prompt (which lives in the
    # Dify flow, mirrored in config/llm for the offline router).
    assert req.system == "ORIGINAL-SYSTEM"      # system unchanged (no founder)
    assert "创始人画像" in req.user             # founder injected into user
    assert "蒙语" in req.user                    # the moat edge reaches the prompt
    # original user content still present after the injected block
    assert req.user.strip().endswith("user text")


def test_build_request_respects_skip_founder():
    cfg = {"system": "ONLY-THIS", "skip_founder": True}
    req = build_request("i1", "u", cfg)
    assert req.system == "ONLY-THIS"
    assert "创始人画像" not in req.system


def test_distribution_fit_lifts_founder_reachable_audiences():
    from idea_core.models import IdeaCandidate
    from idea_core.factors import distribution_fit

    def _c(target_user):
        return IdeaCandidate(
            id="x", signal_id="s", source="external_event", title="t",
            pain="manual work", solution="a tool", target_user=target_user,
            observed_on="2026-06-01", category=None,
        )

    # audiences the founder can reach cheaply (from profile) should outscore a
    # cold, channel-less audience
    reachable = _c("企业安全团队与云厂商采购")     # 安全/云 from profile
    mongolian = _c("内蒙古说蒙语的本地用户")        # 蒙语/内蒙古 edge from profile
    cold = _c("随机的陌生消费者")
    assert distribution_fit(reachable) > distribution_fit(cold)
    assert distribution_fit(mongolian) > distribution_fit(cold)


def test_profile_json_is_valid():
    # guard against a malformed founder.json silently disabling injection
    with open("config/founder.json", encoding="utf-8") as fh:
        json.load(fh)
