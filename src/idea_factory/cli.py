"""单 CLI ``idea``:run(漏斗)/ retro / stats / calibrate。薄壳:解析参数 → 调 pipeline。"""

from __future__ import annotations

import argparse
from datetime import date

from idea_factory.contract.models import SOURCE_BRAIN, SOURCE_EXTERNAL, SOURCE_PERSONA
from idea_factory.contract.stage import STAGES
from idea_factory.runtime.llm import PendingHandoff, get_backend, load_dotenv, load_step_config

_SOURCE_CHOICES = [SOURCE_EXTERNAL, SOURCE_BRAIN, SOURCE_PERSONA]
_BACKENDS = ["none", "router", "cc", "mock", "dify"]
_SUBCOMMANDS = ("run", "retro", "stats", "calibrate")


def _build_run_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea run",
        description="Run the eight-stage funnel (or any contiguous slice of it).",
    )
    p.add_argument("--from", dest="from_stage", choices=STAGES, default=None,
                   help="start stage (resumes from the previous stage's artifact on disk)")
    p.add_argument("--to", dest="to_stage", choices=STAGES, default=None, help="end stage (inclusive)")
    p.add_argument("--only", choices=STAGES, default=None, help="run exactly one stage")
    p.add_argument("--data-dir", default="data", help="input/ledger data directory (default: data)")
    p.add_argument("--output-dir", default="data/processed", help="stage artifacts directory")
    p.add_argument("--date", default=None, help="reference date (ISO); default: today")
    p.add_argument("--top-n", type=int, default=15, help="digest size (ideas.md / memo survivors)")
    p.add_argument("--weekly-top-n", type=int, default=3, help="weekly report size (default: 3)")
    p.add_argument("--sources", nargs="+", choices=_SOURCE_CHOICES, default=None,
                   help="subset of recall sources (default: all enabled)")
    p.add_argument("--floor", type=float, default=None, help="diligence kill-gate floor")
    p.add_argument("--max-pursue-frac", type=float, default=None,
                   help="forced-distribution cap on the pursue fraction per batch")
    p.add_argument("--live", action="store_true", default=False,
                   help="allow network in recall/enrich fetchers (default: offline)")
    p.add_argument("--use-state", action="store_true", default=False,
                   help="dynamic mode: cross-day SeenStore dedup + trend series + derived personas")
    p.add_argument("--no-critique", dest="critique", action="store_false", default=True,
                   help="skip the devil's advocate pass before the judge")
    p.add_argument("--no-version", dest="version", action="store_false", default=True,
                   help="skip snapshotting this run into <output-dir>/versions/")
    p.add_argument("--generate-backend", choices=["rule"] + _BACKENDS[1:], default="rule",
                   help="③generate: rule (offline default, zero token) / router / cc / mock / dify")
    p.add_argument("--judge-backend", choices=_BACKENDS, default="none",
                   help="⑥diligence critique+judge: none (rule-only default) / router / cc / mock / dify")
    p.add_argument("--persona-backend", choices=["static"] + _BACKENDS[1:], default="static",
                   help="①recall 源③人群合成: static (default) / router / cc / mock / dify")
    p.add_argument("--persona-pressure-backend", choices=_BACKENDS, default="none",
                   help="⑥diligence persona 压力测试(advisory): none (default) / router / cc / mock / dify")
    return p


def _build_retro_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea retro",
        description="Record a real-world smoke-test result (the only ground truth this system has).",
    )
    p.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    p.add_argument("--candidate", required=True, help="candidate/idea id being reported on")
    p.add_argument("--metric", required=True, help="metric name (e.g. signups, preorders)")
    p.add_argument("--actual", type=float, required=True, help="the real value observed")
    p.add_argument("--target", type=float, default=None, help="what the verdict predicted")
    p.add_argument("--horizon-days", type=int, default=None, help="prediction horizon in days")
    p.add_argument("--first-revenue", type=float, default=None, help="first real revenue, if any")
    p.add_argument("--lesson", default="", help="one-line takeaway (zero-token, wins if given)")
    p.add_argument("--tested-at", default=None, help="ISO date the test was run; default: today")
    p.add_argument("--llm-lesson-backend", choices=_BACKENDS, default="none",
                   help="when --lesson is empty, extract a one-line lesson via LLM")
    return p


def _build_stats_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idea stats",
        description="Read-only funnel/tier/prediction-error report computed from data/ledger/.",
    )
    p.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    return p


def _build_calibrate_parser() -> argparse.ArgumentParser:
    from idea_factory.stages.retro import calibrate as calibrate_mod

    p = argparse.ArgumentParser(
        prog="idea calibrate",
        description=(
            "Read-only: correlate factors with real-world outcome performance. "
            "Never writes to any config -- prints a suggestion for you to apply by hand."
        ),
    )
    p.add_argument("--data-dir", default="data", help="root data dir (ledger lives under here)")
    p.add_argument("--min-sample", type=int, default=calibrate_mod.DEFAULT_MIN_SAMPLE,
                   help="minimum usable outcomes before a suggestion is given (default: 10)")
    return p


def _report_handoff(ph: PendingHandoff) -> int:
    """Print instructions for the manual Claude Code (CC) handoff and pause."""
    response_path = ph.request_path.parent / ph.request_path.name.replace(
        ".request.jsonl", ".response.jsonl"
    )
    step = ph.request_path.name.split("-", 1)[0] or "LLM"
    print(f"\n⏸  {step} step paused for a manual Claude Code session (Max pool — no programmatic CC).")
    print(f"   request pack: {ph.request_path}  ({ph.count} items)")
    print("   1) open Claude Code by hand in this repo (or run /run-llm-batch)")
    print(f"   2) process the whole batch, writing responses to {response_path}")
    print("   3) re-run this command to resume.")
    return 2


def _run_main(argv: list[str]) -> int:
    from idea_factory import pipeline

    args = _build_run_parser().parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()

    try:
        result = pipeline.run(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            today=today,
            from_stage=args.from_stage,
            to_stage=args.to_stage,
            only=args.only,
            sources=args.sources,
            top_n=args.top_n,
            weekly_top_n=args.weekly_top_n,
            floor=args.floor,
            max_pursue_frac=args.max_pursue_frac,
            live=args.live,
            use_state=args.use_state,
            critique=args.critique,
            version=args.version,
            generate_backend=args.generate_backend,
            judge_backend=args.judge_backend,
            persona_backend=args.persona_backend,
            persona_pressure_backend=args.persona_pressure_backend,
        )
    except PendingHandoff as ph:
        return _report_handoff(ph)

    print(f"run {result.run_id} ({result.week})")
    for s in result.stages:
        killed = f" · killed {s.killed}" if s.killed else ""
        print(f"  {s.stage:<10} {s.entered:>4} → {s.survived:<4}{killed}   {s.artifact or ''}")
    pf = result.stage("portfolio")
    if pf:
        print(
            f"verdicts: {pf.extra.get('pursue', 0)} pursue · {pf.extra.get('review', 0)} review "
            f"· {pf.extra.get('killed', 0)} killed"
        )
        print(f"wrote {pf.extra.get('memos')} and {pf.extra.get('weekly_report')}")
        if pf.extra.get("version_id"):
            print(f"committed version {pf.extra['version_id']}")
    return 0


def _retro_llm_backend(name: str, candidate: str, tested_at: str):
    if name == "cc":
        return get_backend("cc", job_dir="data/llm_jobs", job_name=f"retro-lesson-{candidate}-{tested_at}")
    if name == "dify":
        return get_backend("dify", step="retro_lesson")
    return get_backend(name)


def _retro_main(argv: list[str]) -> int:
    from idea_factory.stages.retro import outcomes as retro_mod

    args = _build_retro_parser().parse_args(argv)
    tested_at = args.tested_at or date.today().isoformat()

    llm = None
    if not args.lesson and args.llm_lesson_backend != "none":
        llm = _retro_llm_backend(args.llm_lesson_backend, args.candidate, tested_at)

    try:
        outcome = retro_mod.record_outcome(
            args.data_dir,
            candidate_id=args.candidate,
            tested_at=tested_at,
            metric=args.metric,
            actual_value=args.actual,
            target=args.target,
            horizon_days=args.horizon_days,
            first_revenue=args.first_revenue,
            lesson=args.lesson,
            llm=llm,
            llm_config=load_step_config("retro_lesson") if llm is not None else None,
        )
    except PendingHandoff as ph:
        return _report_handoff(ph)

    err = retro_mod.prediction_error(outcome.to_dict())
    print(f"recorded outcome for {args.candidate}: {args.metric}={args.actual} (tested {tested_at})")
    if err is not None:
        print(f"  prediction error: {err:+.1%} vs target {args.target}")
    if outcome.lesson:
        print(f"  lesson: {outcome.lesson}")
    return 0


def _stats_main(argv: list[str]) -> int:
    from idea_factory.stages.retro import stats as stats_mod

    args = _build_stats_parser().parse_args(argv)
    print(stats_mod.format_report(stats_mod.funnel_report(args.data_dir)))
    return 0


def _calibrate_main(argv: list[str]) -> int:
    from idea_factory.stages.retro import calibrate as calibrate_mod

    args = _build_calibrate_parser().parse_args(argv)
    report = calibrate_mod.suggest_weights(args.data_dir, min_sample=args.min_sample)
    print(calibrate_mod.format_calibration(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    if argv is None:
        import sys

        argv = sys.argv[1:]
    if not argv or argv[0] not in _SUBCOMMANDS:
        print("usage: idea {run,retro,stats,calibrate} [options]   (idea <cmd> --help for details)")
        # 裸 `idea` 或未知子命令:默认跑全漏斗,保持"一条命令出结果"的手感。
        if argv and argv[0].startswith("-"):
            return _run_main(argv)
        if argv:
            return 2
        return _run_main([])
    cmd, rest = argv[0], argv[1:]
    if cmd == "run":
        return _run_main(rest)
    if cmd == "retro":
        return _retro_main(rest)
    if cmd == "stats":
        return _stats_main(rest)
    return _calibrate_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
