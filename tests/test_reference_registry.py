"""reference/sources.yaml 注册表不变式(仿 test_dify_mirror_invariant 的先例)。

钉死 reference-miner 机制的机器可校验部分:字段齐全、id 唯一且 kebab-case、
lanes/status 枚举合法、license 禁区源(mirror:false)绝无代码镜像、
已建镜像的源必须有 ref 和 miners/<id>.md 沉淀文档。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")  # dev 依赖(pyyaml),与 dify 镜像测试同款

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "reference"

VALID_LANES = {
    "recall", "triage", "generate", "rank", "enrich", "diligence", "portfolio",
    "retro", "llm-infra", "observability",
}
VALID_STATUS = {"adopt", "concepts-borrow", "watch"}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _sources() -> list[dict]:
    data = yaml.safe_load((REF / "sources.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict) and isinstance(data.get("sources"), list)
    return data["sources"]


def test_registry_entries_are_well_formed():
    seen: set[str] = set()
    for s in _sources():
        sid = s.get("id", "<missing>")
        for field in ("id", "repository", "license", "lanes", "status", "mined_for", "note"):
            assert field in s, f"{sid}: 缺必填字段 {field}"
        assert _ID_RE.match(s["id"]), f"{sid}: id 必须 kebab-case"
        assert s["id"] not in seen, f"{sid}: id 重复"
        seen.add(s["id"])
        assert s["status"] in VALID_STATUS, f"{sid}: 非法 status {s['status']}"
        assert set(s["lanes"]) <= VALID_LANES, f"{sid}: 非法 lane {set(s['lanes']) - VALID_LANES}"
        mf = s["mined_for"]
        assert isinstance(mf, dict) and mf and set(mf) <= {"d", "m"}, (
            f"{sid}: mined_for 必须是非空 dict,键 ⊆ {{d,m}}"
        )


def test_license_forbidden_sources_have_no_code_mirror():
    """mirror:false = license 禁区(AGPL/NC/RAIL):只读文档,绝不镜像代码。"""
    for s in _sources():
        if s.get("mirror") is False:
            path = REF / "mirrors" / s["id"]
            assert not path.exists(), f"{s['id']}: mirror:false 但存在代码镜像 {path}"
            assert "ref" not in s, f"{s['id']}: mirror:false 不应有 ref(没有镜像可钉)"


def test_mirrored_sources_are_pinned_and_have_miner_doc():
    """已建镜像的源:ref 必须回写(钉 commit 消费),且 miners/<id>.md 沉淀文档存在。"""
    by_id = {s["id"]: s for s in _sources()}
    mirrors = REF / "mirrors"
    if not mirrors.exists():
        return
    for d in mirrors.iterdir():
        if not d.is_dir() and not d.is_file():  # submodule gitlink shows as dir
            continue
        sid = d.name
        assert sid in by_id, f"镜像 {sid} 未在 sources.yaml 登记"
        assert by_id[sid].get("ref"), f"{sid}: 有镜像但 sources.yaml 无 ref(跑 sync-source.sh {sid})"
        assert (REF / "miners" / f"{sid}.md").exists(), (
            f"{sid}: 有镜像但缺 miners/{sid}.md(cp reference/miner-template.md 起步)"
        )


def test_every_ref_matches_a_mirror():
    """登记了 ref 的源必须真有镜像目录(防手填假 ref)。"""
    for s in _sources():
        if s.get("ref"):
            assert (REF / "mirrors" / s["id"]).exists(), (
                f"{s['id']}: 有 ref 但无镜像目录 —— ref 只能由 sync-source.sh 回写"
            )
