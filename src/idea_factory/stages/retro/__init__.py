"""⑧retro —— 回流:预测 vs 实际,让系统随时间变准(CLI 侧,不在 `idea run` 漏斗里)。

* .outcomes   记录真实冒烟测试结果(唯一的 ground truth)+ LLM lesson 提炼(可选)
* .stats      只读漏斗/判决/预测误差报告(读三张 ledger 纯代码计算)
* .calibrate  只读因子↔结果相关性建议(样本不足明确拒绝;永不写配置)

入口:`idea retro / idea stats / idea calibrate`。只 import contract / runtime / factors。
"""

from __future__ import annotations

from . import calibrate, outcomes, stats  # noqa: F401
