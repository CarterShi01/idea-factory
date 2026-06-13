"""信号源适配器层 —— 沿用 idea_core.llm 的「Protocol + 注册表 + 工厂」范式。

每个源实现 :class:`SourceAdapter`，产出 normalize 能吃的 raw ``dict`` 列表。新增一个
源 = 加一个文件 + 在 ``config/sources.json`` 里登记，不动管线。

约束：
- **离线契约**：网络只在 ``ctx.live=True`` 时发生；默认（demo / 测试）所有适配器要么读
  ``data/raw`` 静态 fixture、要么返回 ``[]``，绝不触网。
- **单源隔离**：某个源失败不应拖垮整批（调度方 catch）。
- **零 token**：抓取层不调用 LLM；需要 LLM 的源（如源③合成）把 ``needs_llm=True``，
  其 LLM 步走 idea_core.llm 的批处理后端，不在这里发起。
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable


# --- 注入式 HTTP（默认 stdlib urllib；测试可传桩，绝不真触网） ----------------

def _default_get_json(url: str, *, headers: dict | None = None, timeout: int = 20):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "idea-factory/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — configured URL
        return json.loads(resp.read().decode("utf-8"))


def _default_get_text(url: str, *, headers: dict | None = None, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "idea-factory/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


# --- 上下文 ----------------------------------------------------------------

@dataclass
class CollectContext:
    raw_dir: Path
    cache_dir: Path
    config: dict = field(default_factory=dict)   # config/sources.json 里该源的段
    live: bool = False                           # True 才允许触网
    get_json: Callable = _default_get_json
    get_text: Callable = _default_get_text


# --- 适配器协议 + 注册表 ----------------------------------------------------

@runtime_checkable
class SourceAdapter(Protocol):
    name: str           # 'static_external' / 'hn_algolia' / 'brain' / 'persona' / 'vps_browser'
    source: str         # SOURCE_EXTERNAL / SOURCE_BRAIN / SOURCE_PERSONA
    needs_llm: bool

    def collect(self, ctx: CollectContext) -> list[dict]:
        ...


REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter) -> SourceAdapter:
    REGISTRY[adapter.name] = adapter
    return adapter


# --- 小工具（适配器复用） ---------------------------------------------------

def read_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


_LOADED = False


def ensure_loaded() -> None:
    """导入内置适配器以触发注册（幂等）。"""
    global _LOADED
    if _LOADED:
        return
    from . import static_external, brain, persona, hn_algolia, vps_browser  # noqa: F401
    _LOADED = True
