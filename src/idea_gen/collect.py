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


def collect_all(
    data_dir: str | Path = "data",
    sources: list[str] | None = None,
    live: bool = False,
    config: dict | None = None,
) -> list[dict]:
    """从(全部或子集)信号源采集 raw 记录。

    ``sources`` 可按 ``SOURCE_*`` 常量或适配器 ``name`` 过滤;``None`` = 全部启用的源。
    ``live=True`` 才允许联网型适配器触网。单源失败被隔离(不影响其它源)。
    """
    ensure_loaded()
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    cache_dir = data_dir / "cache"
    cfg = config or _load_sources_config()

    records: list[dict] = []
    for name, adapter in REGISTRY.items():
        section = cfg.get(name, {})
        if not section.get("enabled", True):
            continue
        if sources and adapter.source not in sources and name not in sources:
            continue
        ctx = CollectContext(raw_dir=raw_dir, cache_dir=cache_dir, config=section, live=live)
        try:
            records.extend(adapter.collect(ctx))
        except Exception:  # noqa: BLE001 — 单源隔离:一个源挂掉不拖垮整批
            continue
    return records
