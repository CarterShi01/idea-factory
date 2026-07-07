"""idea_core.ledger -- the three append-only logs behind the recsys-funnel redesign.

Per ``docs/design/pipeline-v2-plan.md`` §4: the funnel (recall -> triage ->
generate -> rank -> enrich -> diligence -> portfolio -> retro) only gets better
over time if every stage transition and every human action is written down as a
label. Three logs, one writer:

* ``impressions.jsonl`` -- every entity entering/surviving/being killed at a
  stage: ``{run_id, week, stage, entity_id, event, killed_by, ts}``. This is
  what the funnel view (per-stage counts, per-channel survival rate) is built
  from.
* ``verdicts.jsonl`` -- full diligence verdicts + human override events
  (star / kill / override) with ``actor`` set to ``"system"`` or ``"founder"``.
* ``outcomes.jsonl`` -- real-world smoke-test results the founder records
  (:mod:`idea_eval.retro`), the only ground truth the system has.

Plus a **trace** directory, one JSONL per (run_id, stage), recording every LLM
call's prompt/response so a single idea's whole life can be replayed in the UI.

Design constraints (mirroring the rest of this codebase):

* stdlib only, append-only, best-effort. A ledger write must never raise and
  break a pipeline run -- these logs are an *observability* layer, not a
  transactional store. Every public writer swallows I/O errors.
* ``run_id`` is deterministic given ``(today_iso, kind)`` plus a counter on
  disk, mirroring :mod:`idea_core.versioning`'s ``next_version_id`` so repeated
  runs on the same day get distinct, sortable ids and tests stay deterministic
  (no wall-clock reads at import/call time beyond what the caller passes in).
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from idea_factory.contract.models import Outcome  # single source of truth for the Outcome shape

_LEDGER_DIRNAME = "ledger"
_TRACES_DIRNAME = "traces"

IMPRESSIONS = "impressions.jsonl"
VERDICTS = "verdicts.jsonl"
OUTCOMES = "outcomes.jsonl"

# impressions.jsonl event kinds
ENTERED = "entered"
SURVIVED = "survived"
KILLED = "killed"


def ledger_dir(data_dir: str | Path = "data") -> Path:
    return Path(data_dir) / _LEDGER_DIRNAME


def _append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON record as a line. Best-effort: never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_jsonl(path: str | Path) -> list[dict]:
    """Read all records from a jsonl log. Missing file / bad lines -> skipped."""
    path = Path(path)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def next_run_id(data_dir: str | Path, today_iso: str, kind: str = "run") -> str:
    """Next run id for ``today_iso`` -- ``f"{kind}-{today_iso}-{N}"``.

    Scans ``impressions.jsonl`` for existing run_ids of that day/kind so two
    runs on the same day get distinct ids, mirroring
    :func:`idea_core.versioning.next_version_id`.
    """
    prefix = f"{kind}-{today_iso}-"
    max_n = 0
    for rec in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS):
        run_id = rec.get("run_id", "")
        if isinstance(run_id, str) and run_id.startswith(prefix):
            try:
                max_n = max(max_n, int(run_id[len(prefix):]))
            except ValueError:
                continue
    return f"{prefix}{max_n + 1}"


# --- impressions -----------------------------------------------------------


def log_impression(
    data_dir: str | Path,
    run_id: str,
    week: str,
    stage: str,
    entity_id: str,
    event: str,
    killed_by: str | None = None,
    ts: str | None = None,
    **extra,
) -> None:
    """Log one stage transition for one entity (signal or candidate id).

    ``event`` is one of :data:`ENTERED` / :data:`SURVIVED` / :data:`KILLED`.
    ``ts`` should be supplied by the caller (an explicit reference date/time) --
    this module never reads the wall clock itself, so replays/tests stay
    deterministic.
    """
    record = {
        "run_id": run_id,
        "week": week,
        "stage": stage,
        "entity_id": entity_id,
        "event": event,
        "killed_by": killed_by,
        "ts": ts,
    }
    record.update(extra)
    _append_jsonl(ledger_dir(data_dir) / IMPRESSIONS, record)


def log_impressions_bulk(
    data_dir: str | Path,
    run_id: str,
    week: str,
    stage: str,
    survived_ids: list[str],
    killed: dict[str, str],
    ts: str | None = None,
) -> None:
    """Convenience: log a whole stage's outcome in one call.

    ``killed`` maps entity_id -> killed_by reason. Every id in ``survived_ids``
    is logged as :data:`SURVIVED`; every key in ``killed`` as :data:`KILLED`.
    """
    for eid in survived_ids:
        log_impression(data_dir, run_id, week, stage, eid, SURVIVED, ts=ts)
    for eid, reason in killed.items():
        log_impression(data_dir, run_id, week, stage, eid, KILLED, killed_by=reason, ts=ts)


def channel_survival_rates(
    data_dir: str | Path, stage: str | None = None, run_id: str | None = None
) -> dict[str, dict]:
    """From impressions.jsonl: per (stage,) survived/killed counts and rate.

    Returns ``{stage: {"survived": n, "killed": n, "rate": survived/(survived+killed)}}``.
    ``run_id`` (optional) filters to one run's impressions -- default None keeps
    the all-runs aggregate the stats view / older callers rely on.
    """
    counts: dict[str, dict[str, int]] = {}
    for rec in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS):
        if run_id is not None and rec.get("run_id") != run_id:
            continue
        st = rec.get("stage", "")
        if stage is not None and st != stage:
            continue
        bucket = counts.setdefault(st, {"survived": 0, "killed": 0})
        if rec.get("event") == KILLED:
            bucket["killed"] += 1
        elif rec.get("event") == SURVIVED:
            bucket["survived"] += 1
    out: dict[str, dict] = {}
    for st, c in counts.items():
        total = c["survived"] + c["killed"]
        out[st] = {**c, "rate": round(c["survived"] / total, 4) if total else 0.0}
    return out


def killed_by_breakdown(
    data_dir: str | Path, stage: str | None = None, run_id: str | None = None
) -> dict[str, int]:
    """Count of kills per ``killed_by`` reason (e.g. 'stale_24m', 'profile_mismatch').

    ``run_id`` (optional) filters to one run -- default None = all-runs aggregate.
    """
    counts: dict[str, int] = {}
    for rec in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS):
        if rec.get("event") != KILLED:
            continue
        if stage is not None and rec.get("stage") != stage:
            continue
        if run_id is not None and rec.get("run_id") != run_id:
            continue
        reason = rec.get("killed_by") or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return counts


# --- run discovery (for the studio run-centric views) ------------------------


def _run_sort_key(run_id: str) -> tuple:
    """Sort key for ``{kind}-YYYY-MM-DD-N`` ids: by (date, N) so newest is last.

    Falls back to the raw string when the shape is unexpected (still deterministic).
    """
    m = re.match(r"^(.*)-(\d{4}-\d{2}-\d{2})-(\d+)$", run_id or "")
    if m:
        return (m.group(2), int(m.group(3)), m.group(1))
    return ("", 0, run_id or "")


def list_runs(data_dir: str | Path) -> list[str]:
    """All distinct run_ids seen in impressions + the traces/ tree, oldest→newest."""
    ids: set[str] = set()
    for rec in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS):
        rid = rec.get("run_id")
        if isinstance(rid, str) and rid:
            ids.add(rid)
    traces_root = ledger_dir(data_dir) / _TRACES_DIRNAME
    if traces_root.exists():
        for d in traces_root.iterdir():
            if d.is_dir():
                ids.add(d.name)
    return sorted(ids, key=_run_sort_key)


def stages_for_run(data_dir: str | Path, run_id: str) -> list[str]:
    """Stages this run touched: impression stages + trace file stems, in funnel order."""
    from idea_factory.contract.stage import STAGES

    seen: set[str] = set()
    for rec in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS):
        if rec.get("run_id") == run_id and rec.get("stage"):
            seen.add(rec["stage"])
    traces_dir = ledger_dir(data_dir) / _TRACES_DIRNAME / run_id
    if traces_dir.exists():
        for f in traces_dir.glob("*.jsonl"):
            seen.add(f.stem)
    ordered = [s for s in STAGES if s in seen]
    ordered += sorted(s for s in seen if s not in STAGES)  # ask/critique/etc appended
    return ordered


def impressions_for_run(data_dir: str | Path, run_id: str) -> list[dict]:
    """Raw impression rows for one run (stage-drill + lineage joins)."""
    return [r for r in read_jsonl(ledger_dir(data_dir) / IMPRESSIONS) if r.get("run_id") == run_id]


# --- verdicts ----------------------------------------------------------------


def log_verdict(data_dir: str | Path, verdict: dict, actor: str = "system", ts: str | None = None) -> None:
    """Append one diligence verdict (or a founder override event) to verdicts.jsonl.

    ``verdict`` is typically an :class:`idea_eval.evaluate.Evaluation`'s
    ``to_dict()`` output plus whatever the caller adds; ``actor`` distinguishes
    the system's own judge output from a founder's manual star/kill/override --
    the founder's clicks are this system's most valuable label.
    """
    record = dict(verdict)
    record["actor"] = actor
    record.setdefault("ts", ts)
    _append_jsonl(ledger_dir(data_dir) / VERDICTS, record)


def log_founder_action(
    data_dir: str | Path,
    candidate_id: str,
    action: str,
    ts: str | None = None,
    **extra,
) -> None:
    """Log a founder UI action (star / kill / override_verdict / ...) as a label event."""
    record = {"candidate_id": candidate_id, "event": f"founder_{action}", "actor": "founder", "ts": ts}
    record.update(extra)
    _append_jsonl(ledger_dir(data_dir) / VERDICTS, record)


# --- outcomes ----------------------------------------------------------------
# Outcome itself lives in idea_core.models (shared shape with Evidence); this
# module only re-exports it so callers can do ``ledger.Outcome`` for symmetry
# with ``ledger.log_outcome`` / ``ledger.read_outcomes`` without an extra import.


def log_outcome(data_dir: str | Path, outcome: Outcome) -> None:
    _append_jsonl(ledger_dir(data_dir) / OUTCOMES, outcome.to_dict())


def read_outcomes(data_dir: str | Path) -> list[dict]:
    return read_jsonl(ledger_dir(data_dir) / OUTCOMES)


# --- traces ------------------------------------------------------------------


def trace_path(data_dir: str | Path, run_id: str, stage: str) -> Path:
    return ledger_dir(data_dir) / _TRACES_DIRNAME / run_id / f"{stage}.jsonl"


def log_trace(
    data_dir: str | Path,
    run_id: str,
    stage: str,
    entity_id: str,
    prompt_version: str,
    request: dict,
    response: dict,
    model: str = "",
    ts: str | None = None,
    usage: dict | None = None,
    cost: float | None = None,
    latency_ms: float | None = None,
) -> None:
    """Record one LLM call's prompt+response for the single-idea trace view.

    ``usage`` ({prompt_tokens, completion_tokens, total_tokens}), ``cost`` (¥, or
    None when the model has no price), and ``latency_ms`` are optional and null on
    the offline/mock path -- so the cost-gradient panel is measurable when a real
    backend runs, without changing anything on the zero-token default path.
    """
    record = {
        "entity_id": entity_id,
        "prompt_version": prompt_version,
        "request": request,
        "response": response,
        "model": model,
        "ts": ts,
        "usage": usage,
        "cost": cost,
        "latency_ms": latency_ms,
    }
    _append_jsonl(trace_path(data_dir, run_id, stage), record)


def read_trace(data_dir: str | Path, run_id: str, stage: str) -> list[dict]:
    return read_jsonl(trace_path(data_dir, run_id, stage))


def today_iso() -> str:
    """Convenience default; never called implicitly (mirrors versioning.today_iso)."""
    return date.today().isoformat()


def now_iso() -> str:
    """Convenience default for a full timestamp; never called implicitly."""
    return datetime.now().isoformat(timespec="seconds")


def week_of(day_iso: str) -> str:
    """ISO year-week label ('2026-W27') for grouping impressions into weekly batches."""
    try:
        y, w, _ = date.fromisoformat(day_iso).isocalendar()
        return f"{y}-W{w:02d}"
    except ValueError:
        return day_iso
