"""Stage 1 -- 采集:适配器分发器(配置驱动 + 注册表)。

历史上这里是三个写死的文件读取;现在升级为「适配器协议 + 配置驱动」(见
:mod:`idea_gen.sources`)。``collect_all`` 的签名与产出对**离线默认路径保持不变**
(只读 ``data/raw``、零网络),所以现有 pipeline / Studio / 测试无感。

动态:传 ``live=True`` 时,联网型适配器(hn_algolia / vps_browser …)才真正抓取;
默认 ``live=False`` 时它们返回 ``[]``,等价于原来的纯离线行为。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .sources import REGISTRY, CollectContext, ensure_loaded

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_sources_config() -> dict:
    path = Path(os.environ.get("IDEA_SOURCES_CONFIG", _REPO_ROOT / "config" / "sources.json"))
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    # 兜底:三个静态源默认开,联网源默认关
    return {"static_external": {}, "brain": {}, "persona": {}}


def _cap_english_by_heat(records: list[dict], top_n: int) -> list[dict]:
    """英文 HN 记录(source_name=='hn')按 points 降序只留前 top_n;其余源全保留。
    top_n<=0 表示不截断。稳定:非 hn 记录保持原顺序,hn 记录按热度挑出后接在其后。"""
    if top_n is None or top_n <= 0:
        return records
    hn = [r for r in records if r.get("source_name") == "hn"]
    if len(hn) <= top_n:
        return records
    keep = set(id(r) for r in sorted(hn, key=lambda r: r.get("points", 0), reverse=True)[:top_n])
    return [r for r in records if r.get("source_name") != "hn" or id(r) in keep]


def collect_all(
    data_dir: str | Path = "data",
    sources: list[str] | None = None,
    live: bool = False,
    config: dict | None = None,
    persona_llm: object = None,
) -> list[dict]:
    """从(全部或子集)信号源采集 raw 记录。

    ``sources`` 可按 ``SOURCE_*`` 常量或适配器 ``name`` 过滤;``None`` = 全部启用的源。
    ``live=True`` 才允许联网型适配器触网。``persona_llm`` 给定时,源③(pain_persona)用它
    做 grounded 合成(否则走静态)。**两遍采集**:先采源①②,再把其结果作为 grounding 喂源③。
    单源失败被隔离(不影响其它源)。
    """
    from idea_core.models import SOURCE_PERSONA

    ensure_loaded()
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    cache_dir = data_dir / "cache"
    cfg = config or _load_sources_config()

    def _wanted(adapter, name) -> bool:
        if not cfg.get(name, {}).get("enabled", True):
            return False
        if sources and adapter.source not in sources and name not in sources:
            return False
        return True

    # 第一遍:源①②(非 persona)
    peer: list[dict] = []
    for name, adapter in REGISTRY.items():
        if adapter.source == SOURCE_PERSONA or not _wanted(adapter, name):
            continue
        ctx = CollectContext(raw_dir=raw_dir, cache_dir=cache_dir, config=cfg.get(name, {}), live=live)
        try:
            peer.extend(adapter.collect(ctx))
        except Exception:  # noqa: BLE001 — 单源隔离
            continue

    # 英文 HN 洪水治理:只保留热度(points)最高的前 N 条英文信号,防止实时 HN 淹没
    # 中文市场人群(源③)。默认 20,可在 sources.json 的 hn_algolia.hot_top_n 调。
    peer = _cap_english_by_heat(peer, int(cfg.get("hn_algolia", {}).get("hot_top_n", 20)))

    # 第二遍:源③(persona),拿第一遍结果作 grounding
    records: list[dict] = list(peer)
    for name, adapter in REGISTRY.items():
        if adapter.source != SOURCE_PERSONA or not _wanted(adapter, name):
            continue
        ctx = CollectContext(
            raw_dir=raw_dir, cache_dir=cache_dir, config=cfg.get(name, {}),
            live=live, llm=persona_llm, peer_records=peer,
        )
        try:
            records.extend(adapter.collect(ctx))
        except Exception:  # noqa: BLE001
            continue
    return records
