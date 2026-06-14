#!/usr/bin/env python3
"""Self-iteration round reporter — measure one gen→eval round so rounds compare.

The 3-round self-iteration loop (毒舌投资人 + 创始人画像) needs an *objective*
scorecard per round, otherwise "是否变好了" is just vibes. This reads a round's
``ideas.json`` (+ optional ``screened.json``) and prints the metrics the brutal
investor keeps hammering:

* verdict mix (pursue/review/kill) and kill-rate — a meaner critic should kill more;
* Non-Duplicate Ratio of the Top-N digest (投资人复评 #3: 近重挤占);
* factor spread (build_cost / moat_signal must NOT be flat — 投资人复评 #1);
* founder-fit coverage — how many ideas land on the founder's reachable channels;
* fusion coverage — how many candidates are three-source fusions (mission 护城河).

stdlib only. Usage:
    PYTHONPATH=src python3 scripts/round_report.py \
        --ideas data/processed/ideas.json \
        --screened data/processed/screened.json \
        --label round1 [--top-n 15]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

_WORD_RE = re.compile(r"[a-z0-9]+|[一-鿿]")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _non_dup_ratio(items: list[dict], threshold: float = 0.6) -> float:
    """Fraction of the list that is NOT a near-duplicate of an earlier item."""
    if not items:
        return 1.0
    toks = [_tokens(f"{i.get('title','')} {i.get('solution','')}") for i in items]
    unique = 0
    seen: list[set[str]] = []
    for t in toks:
        if any(_jaccard(t, s) >= threshold for s in seen):
            continue
        unique += 1
        seen.append(t)
    return round(unique / len(items), 3)


def _spread(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
        "stdev": round(statistics.pstdev(values), 3),
        "distinct": len({round(v, 2) for v in values}),
    }


def _founder_reach_terms() -> set[str]:
    try:
        prof = json.loads(Path("config/founder.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    terms: set[str] = set()
    for k in ("reach_keywords_en", "reach_keywords_zh"):
        terms.update(t.lower() for t in (prof.get(k) or []) if isinstance(t, str))
    return terms


def main() -> None:
    ap = argparse.ArgumentParser(description="Report one self-iteration round's scorecard.")
    ap.add_argument("--ideas", default="data/processed/ideas.json")
    ap.add_argument("--screened", default="data/processed/screened.json")
    ap.add_argument("--label", default="round")
    ap.add_argument("--top-n", type=int, default=15)
    args = ap.parse_args()

    ideas = json.loads(Path(args.ideas).read_text(encoding="utf-8"))
    digest = ideas[: args.top_n]

    print(f"=== {args.label} scorecard ===")
    print(f"candidates: {len(ideas)}  | digest Top-{args.top_n}: {len(digest)}")

    # factor spread (the #1 complaint: build_cost/moat were flat)
    for fac in ("build_cost", "moat_signal", "pain_intensity", "distribution_fit"):
        vals = [i["factors"][fac] for i in ideas if "factors" in i and fac in i["factors"]]
        print(f"  factor {fac:18s}: {_spread(vals)}")

    print(f"  Non-Duplicate Ratio (Top-{args.top_n}): {_non_dup_ratio(digest)}  "
          f"(全量 {_non_dup_ratio(ideas)})")

    # fusion coverage (mission 护城河)
    fused = [i for i in ideas if i.get("fusion_sources")]
    print(f"  三源融合候选: {len(fused)}/{len(ideas)}  "
          f"(digest 内 {sum(1 for i in digest if i.get('fusion_sources'))})")

    # founder-fit coverage
    terms = _founder_reach_terms()
    if terms:
        def _hits(i):
            blob = f"{i.get('title','')} {i.get('target_user','')} {i.get('solution','')}".lower()
            return any(t in blob for t in terms)
        fit = sum(1 for i in digest if _hits(i))
        print(f"  founder-fit(命中可触达渠道) digest: {fit}/{len(digest)}")

    # verdict mix from screened.json (if the eval round was run)
    sp = Path(args.screened)
    if sp.exists():
        scr = json.loads(sp.read_text(encoding="utf-8"))
        mix = {"pursue": 0, "review": 0, "kill": 0}
        for e in scr:
            v = e.get("verdict")
            if v in mix:
                mix[v] += 1
        total = sum(mix.values()) or 1
        print(f"  verdicts: {mix}  kill-rate={round(mix['kill']/total, 3)}")
    else:
        print(f"  (no {sp}; run idea-eval --judge-backend router to get verdicts)")


if __name__ == "__main__":
    main()
