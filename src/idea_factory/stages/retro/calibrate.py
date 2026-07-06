"""idea_eval.calibrate -- outcomes -> factor-weight suggestions (read-only, gated).

Per ``docs/design/pipeline-v2-plan.md`` §9.3 (item #8, deliberately deferred
until now): the correct way to close the retro loop is to compute how each
generation-side factor (:mod:`idea_core.factors`) correlates with real-world
performance -- but only once there's enough outcome data for the number to
mean anything. Tuning ``ranks.DEFAULT_WEIGHTS``/``config/funnel.json`` on 2-3
noisy samples would be worse than not tuning at all.

So this module **never writes anything**. It reads ``outcomes.jsonl`` +
``verdicts.jsonl`` (joined by candidate id), and either:

* returns ``{"status": "insufficient_data", ...}`` below ``min_sample`` --
  explicit, not a silent no-op, so the founder knows *why* nothing is suggested;
* or returns Pearson correlations between each factor and a "performance" score
  (``1 + prediction_error`` -- 1.0 = hit target exactly) for the founder to
  read and decide, by hand, whether to adjust the ranking weights.

Applying a suggestion is a human decision, not something this module does.
"""

from __future__ import annotations

from pathlib import Path

from idea_factory.factors import FACTORS

from . import outcomes as retro_mod

DEFAULT_MIN_SAMPLE = 10


def _performance(outcome: dict) -> float | None:
    """1.0 = hit the predicted target exactly; >1 beat it; <1 missed it."""
    err = retro_mod.prediction_error(outcome)
    return None if err is None else 1.0 + err


def _factors_for(data_dir: str | Path, candidate_id: str) -> dict | None:
    verdict = retro_mod.latest_verdict_for(data_dir, candidate_id)
    factors = verdict.get("factors")
    return factors if isinstance(factors, dict) else None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Plain-stdlib Pearson correlation coefficient; None if undefined (n<2 or
    zero variance in either series)."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x**0.5 * var_y**0.5)


def suggest_weights(data_dir: str | Path, min_sample: int = DEFAULT_MIN_SAMPLE) -> dict:
    """Read-only: correlate each factor with real-world performance.

    Returns either an ``insufficient_data`` report (below ``min_sample`` usable
    samples -- an outcome only counts if it has a numeric ``target`` AND its
    candidate's factors were logged in ``verdicts.jsonl``, i.e. the run went
    through ``require_evidence``/an LLM judge) or an ``ok`` report with a
    ``correlations`` dict. Never writes to any config file.
    """
    from idea_factory.runtime import ledger

    samples: list[tuple[dict, float]] = []
    for o in ledger.read_outcomes(data_dir):
        perf = _performance(o)
        if perf is None:
            continue
        factors = _factors_for(data_dir, o.get("candidate_id", ""))
        if factors is None:
            continue
        samples.append((factors, perf))

    if len(samples) < min_sample:
        return {
            "status": "insufficient_data",
            "count": len(samples),
            "min_sample": min_sample,
            "message": (
                f"样本不足(需要 >= {min_sample} 条带 target 且能查到 factors 的真实结果,"
                f"当前 {len(samples)} 条)——暂不建议调权,继续积累 retro 数据。"
            ),
        }

    correlations: dict[str, float] = {}
    for name in FACTORS:
        xs = [f.get(name, 0.0) for f, _ in samples]
        ys = [perf for _, perf in samples]
        r = _pearson(xs, ys)
        if r is not None:
            correlations[name] = round(r, 4)

    return {
        "status": "ok",
        "count": len(samples),
        "correlations": correlations,
        "message": (
            "样本量足够——以下是各因子与实际表现(1+预测误差)的相关性,供人工决定是否调整 "
            "ranks.DEFAULT_WEIGHTS/config/funnel.json 的权重。本命令只读,不自动写回任何配置。"
        ),
    }


def format_calibration(report: dict) -> str:
    lines = ["# idea-eval calibrate", "", report["message"], ""]
    if report["status"] == "insufficient_data":
        lines.append(f"（{report['count']}/{report['min_sample']}）")
        return "\n".join(lines)
    lines.append(f"样本数：{report['count']}")
    lines.append("")
    for name, r in sorted(report["correlations"].items(), key=lambda kv: -abs(kv[1])):
        sign = "+" if r >= 0 else ""
        lines.append(f"- {name}: {sign}{r:.4f}")
    return "\n".join(lines)
