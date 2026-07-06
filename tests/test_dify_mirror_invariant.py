"""§3.3 不变式(docs/design/dify-prompt-authoring.md):config/llm/<step>.json 的
system 必须与 dify/flows/<step>.yml 对应 LLM 节点的 system 逐字一致。

这条不变式此前只有文档描述,没有代码校验(2026-07-04 的镜像同步 commit 是手工做的)。
本测试把它钉成 CI 规则:漂移即红,不用等下次手工同步时才发现。

只校验 generate/critique/judge 三步(persona_sim 不在 Dify 上,见 dify-integration.md)。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from idea_factory.runtime.llm import load_step_config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _REPO_ROOT / "config" / "llm"
_FLOWS_DIR = _REPO_ROOT / "dify" / "flows"

# step name -> dify flow file stem
_STEP_TO_FLOW = {
    "generate": "idea-gen",
    "critique": "idea-critique",
    "judge": "idea-judge",
}


def _flow_system_text(flow_stem: str) -> str:
    doc = yaml.safe_load((_FLOWS_DIR / f"{flow_stem}.yml").read_text(encoding="utf-8"))
    nodes = doc["workflow"]["graph"]["nodes"]
    llm_node = next(n for n in nodes if n["id"] == "llm")
    prompts = llm_node["data"]["prompt_template"]
    sys_entry = next(p for p in prompts if p["role"] == "system")
    return sys_entry["text"]


def test_all_steps_have_a_mirror_pair():
    for step in _STEP_TO_FLOW:
        assert (_CONFIG_DIR / f"{step}.json").exists()
        assert (_FLOWS_DIR / f"{_STEP_TO_FLOW[step]}.yml").exists()


def test_config_system_matches_dify_flow_system_exactly():
    mismatches = []
    for step, flow_stem in _STEP_TO_FLOW.items():
        cfg_system = load_step_config(step, config_dir=_CONFIG_DIR)["system"]
        flow_system = _flow_system_text(flow_stem)
        if cfg_system != flow_system:
            mismatches.append(step)
    assert not mismatches, (
        f"config/llm/*.json system 与 dify/flows/*.yml 漂移的步骤: {mismatches} —— "
        "按 docs/design/dify-prompt-authoring.md §3.3,改任一处都要同步另一处。"
    )
