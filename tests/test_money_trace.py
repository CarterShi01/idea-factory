"""Tests for the pipeline-v2 Signal.money_trace field (#9)."""

from __future__ import annotations

from idea_factory.contract.models import Signal
from idea_factory.stages.generate.llm import _signal_fields
from idea_factory.stages.recall.normalize import normalize_record


def test_signal_default_money_trace_is_empty():
    s = Signal(id="x", source="external_event", source_name="hn", title="t", raw_text="t", observed_on="2026-06-01")
    assert s.money_trace == ""


def test_normalize_lifts_money_trace_from_raw():
    raw = {"title": "招聘信号", "pain": "p", "money_trace": "近30天17个相关岗位", "observed_on": "2026-06-01"}
    s = normalize_record(raw)
    assert s.money_trace == "近30天17个相关岗位"


def test_normalize_blank_when_absent():
    raw = {"title": "无钱证据信号", "pain": "p", "observed_on": "2026-06-01"}
    s = normalize_record(raw)
    assert s.money_trace == ""


def test_signal_fields_carries_money_trace_with_fallback():
    with_trace = Signal(
        id="a", source="external_event", source_name="jobs", title="t", raw_text="t",
        observed_on="2026-06-01", money_trace="17 个岗位付薪招人",
    )
    assert _signal_fields(with_trace)["money_trace"] == "17 个岗位付薪招人"

    without_trace = Signal(
        id="b", source="external_event", source_name="hn", title="t", raw_text="t", observed_on="2026-06-01",
    )
    assert _signal_fields(without_trace)["money_trace"] == "(无明确付费痕迹)"
