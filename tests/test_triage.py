"""Tests for the triage stage (staleness red-line) + generate's anti-fit screen."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from idea_factory import pipeline
from idea_factory.contract.models import SOURCE_BRAIN, SOURCE_EXTERNAL, IdeaCandidate, Signal
from idea_factory.runtime import ledger
from idea_factory.stages import generate
from idea_factory.stages.triage import rules as triage

_REPO_RAW = Path("data/raw")


def _signal(id_, observed_on) -> Signal:
    return Signal(
        id=id_, source=SOURCE_EXTERNAL, source_name="hn", title="t", raw_text="t",
        observed_on=observed_on,
    )


def test_triage_signals_kills_stale_over_24_months():
    today = date(2026, 7, 5)
    signals = [
        _signal("fresh", "2026-06-01"),     # ~1 month old, survives
        _signal("borderline", "2024-08-01"),  # ~23 months, survives
        _signal("stale", "2023-01-01"),     # ~42 months, killed
    ]
    kept, killed = triage.triage_signals(signals, today)
    assert {s.id for s in kept} == {"fresh", "borderline"}
    assert killed == {"stale": triage.STALE_24M}


def test_triage_signals_tolerates_unparseable_date():
    today = date(2026, 7, 5)
    signals = [_signal("placeholder", "1970-01-01")]
    # 1970-01-01 IS parseable and IS ancient -- it should be killed as stale.
    kept, killed = triage.triage_signals(signals, today)
    assert kept == []
    assert killed == {"placeholder": triage.STALE_24M}

    signals2 = [_signal("blank", "")]
    kept2, killed2 = triage.triage_signals(signals2, today)
    assert kept2[0].id == "blank"
    assert killed2 == {}


def _candidate(id_, *, target_user="", pain="", solution="", source=SOURCE_BRAIN) -> IdeaCandidate:
    return IdeaCandidate(
        id=id_, signal_id="s1", source=source, title="标题",
        pain=pain, solution=solution, target_user=target_user, observed_on="2026-07-01",
    )


def test_anti_fit_screen_kills_explicit_anti_fit_with_no_channel():
    anti_fit = _candidate(
        "anti1",
        target_user="全球开发者",
        pain="获客难",
        solution="靠烧钱买量获客,靠融资续命打持久战,长周期不赚钱也要抢市场",
    )
    kept, killed = generate._screen_anti_fit([anti_fit])
    assert kept == []
    assert killed == {"anti1": generate.ANTI_FIT}


def test_anti_fit_screen_keeps_monopoly_channel_idea():
    good = _candidate(
        "good1",
        target_user="内蒙古蒙语母语中老年人",
        pain="蒙语母语者缺少好用的工具",
        solution="面向蒙语/内蒙古用户的本地化产品,靠家人信任渠道低成本获客",
    )
    kept, killed = generate._screen_anti_fit([good])
    assert killed == {}
    assert [c.id for c in kept] == ["good1"]


def test_anti_fit_screen_keeps_bare_idea_with_no_signal_at_all():
    # No anti-fit language present -> should NOT be hard-killed even though
    # founder_fit is low; the screen only kills *explicit* anti-fit, not "merely low".
    bare = _candidate("bare1", target_user="用户", pain="有点麻烦", solution="做个工具")
    kept, killed = generate._screen_anti_fit([bare])
    assert killed == {}
    assert [c.id for c in kept] == ["bare1"]


def _copy_raw_fixtures(dst_data_dir: Path) -> None:
    (dst_data_dir / "raw").mkdir(parents=True, exist_ok=True)
    for name in ("inbox.jsonl", "personas.json", "sample_signals.json"):
        src = _REPO_RAW / name
        if src.exists():
            shutil.copy2(src, dst_data_dir / "raw" / name)


def test_pipeline_triage_always_on_logs_ledger(tmp_path):
    # 红线与 ledger 常开(从零重构的行为变更):每次跑都记 impressions。
    data_dir = tmp_path / "data"
    _copy_raw_fixtures(data_dir)
    output_dir = tmp_path / "processed"

    result = pipeline.run(
        data_dir=data_dir, output_dir=output_dir, today=date(2026, 7, 5), to_stage="rank",
    )
    assert result.stage("generate").survived >= 0  # pipeline still runs end to end

    rates = ledger.channel_survival_rates(data_dir, stage="triage")
    assert "triage" in rates
    # the 1970-01-01 persona placeholder signal must be stale-killed.
    breakdown = ledger.killed_by_breakdown(data_dir, stage="triage")
    assert breakdown.get(triage.STALE_24M, 0) >= 1
    assert (data_dir / "ledger").exists()
