"""分层隔离不变式(架构的 CI 铁律,仿 test_dify_mirror_invariant 的先例)。

    contract ← runtime ← factors ← stages ← pipeline ← cli

* contract 不 import 包内任何其他层;
* runtime 只 import contract;
* factors 只 import contract + runtime;
* stages/<X> 只 import contract/runtime/factors + 本段自己——**兄弟段互不 import**;
* 组合只发生在 pipeline(cli 只经 pipeline/stages 的公共入口)。

违反其一 = 架构漂移,本测试直接红。
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "idea_factory"


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports_of(path: Path) -> set[str]:
    """Absolute in-package module names imported by this file (both syntax forms,
    relative imports resolved)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    me = _module_name(path)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("idea_factory"):
                    out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module and node.module.startswith("idea_factory"):
                    out.add(node.module)
            else:
                base = me.split(".")
                if path.name != "__init__.py":
                    base = base[:-1]
                base = base[: len(base) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
                if mod.startswith("idea_factory"):
                    out.add(mod)
    return out


def _layer(mod: str) -> str:
    parts = mod.split(".")
    if len(parts) == 1:
        return "root"
    if parts[1] in ("contract", "runtime", "factors"):
        return parts[1]
    if parts[1] == "stages":
        return f"stages.{parts[2]}" if len(parts) > 2 else "stages"
    return parts[1]  # pipeline / cli / __main__


ALLOWED = {
    "contract": {"contract"},
    "runtime": {"contract", "runtime"},
    "factors": {"contract", "runtime", "factors"},
    # 每个段在测试里动态展开:自己 + 三个下层
    "pipeline": None,  # pipeline may import stages (it IS the composer)
    "cli": None,
    "__main__": None,
    "root": None,
}


def test_layering_invariant():
    violations: list[str] = []
    for py in sorted(SRC.rglob("*.py")):
        me = _module_name(py)
        my_layer = _layer(me)
        for imported in _imports_of(py):
            its_layer = _layer(imported)
            if my_layer in ("pipeline", "cli", "__main__", "root"):
                continue  # composers may see everything below them
            if my_layer.startswith("stages."):
                allowed = {"contract", "runtime", "factors", my_layer}
                if its_layer == "stages":  # bare `idea_factory.stages` (namespace only)
                    continue
                if its_layer not in allowed:
                    violations.append(f"{me} → {imported}  (段 {my_layer} 不许碰 {its_layer})")
            else:
                if its_layer not in ALLOWED[my_layer]:
                    violations.append(f"{me} → {imported}  (层 {my_layer} 不许碰 {its_layer})")
    assert not violations, "分层隔离被破坏:\n" + "\n".join(violations)


def test_sibling_stages_never_import_each_other():
    """显式的兄弟段断言(与上面重叠,但失败信息更直白)。"""
    for py in sorted((SRC / "stages").rglob("*.py")):
        me = _module_name(py)
        my_stage = _layer(me)
        for imported in _imports_of(py):
            its = _layer(imported)
            if its.startswith("stages.") and its != my_stage:
                raise AssertionError(f"兄弟段互相 import:{me} → {imported}")
