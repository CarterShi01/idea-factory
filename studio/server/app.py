"""Idea Factory Studio — control-panel backend (stdlib only, zero deps).

A thin web layer over the idea-factory kernel:
  * serves the built React/TS frontend (studio/web/dist) as a SPA
  * exposes a small JSON API that reads the kernel's outputs and triggers runs
  * gates everything behind a single shared password (nginx does NOT auth)

It imports the kernel in-process (idea_factory) — no subprocess, no DB,
no extra runtime. Run:  python studio/server/app.py  (listens 127.0.0.1:3010)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# --- locate repo root and import the kernel -------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = REPO_ROOT / "studio" / "web" / "dist"
DATA_DIR = REPO_ROOT / "data"
PROCESSED = DATA_DIR / "processed"
# Founder profile (config/founder.json) — the pipeline re-reads it every run, so an
# edit saved here automatically takes effect on the next generate/evaluate.
FOUNDER_PATH = REPO_ROOT / "config" / "founder.json"

import sys

sys.path.insert(0, str(REPO_ROOT / "src"))
from idea_factory import pipeline  # noqa: E402
from idea_factory.runtime import ledger, versioning  # noqa: E402
from idea_factory.runtime.llm import (  # noqa: E402
    build_request, get_backend, load_dotenv, load_step_config, render_template,
)
from idea_factory.stages.diligence import gate as diligence_gate  # noqa: E402
from idea_factory.stages.diligence import judge as diligence_judge  # noqa: E402
from idea_factory.stages.recall.collect import collect_all  # noqa: E402
from idea_factory.stages.recall.normalize import normalize  # noqa: E402
from idea_factory.stages.retro import outcomes as retro_outcomes  # noqa: E402
from idea_factory.stages.retro import stats as eval_stats  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

HOST = os.environ.get("STUDIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUDIO_PORT", "3010"))
PASSWORD = os.environ.get("STUDIO_PASSWORD", "")  # empty => auth disabled (dev)
# Machine API key for the read-only /api/top3 endpoint (Bearer token). Empty =>
# endpoint locked (401 for everyone) so it never accidentally serves unauthed.
TOP3_API_KEY = os.environ.get("IDEA_TOP3_API_KEY", "")
_SECRET = (os.environ.get("STUDIO_SECRET") or PASSWORD or "idea-factory-dev").encode()
COOKIE = "studio_session"
SESSION_TTL = 7 * 24 * 3600

# --- tiny signed-cookie auth ---------------------------------------------


def _sign(payload: str) -> str:
    mac = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{mac}"


def _make_token() -> str:
    return _sign(str(int(time.time())))


def _valid_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    payload, _, _mac = token.rpartition(".")
    if _sign(payload) != token:
        return False
    try:
        return (time.time() - int(payload)) < SESSION_TTL
    except ValueError:
        return False


def _auth_enabled() -> bool:
    return bool(PASSWORD)


# --- data helpers ---------------------------------------------------------


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _factor_names() -> list[str]:
    from idea_factory.factors import FACTORS

    return list(FACTORS)


# --- version resolution ---------------------------------------------------
# Reads default to the *latest* version; an explicit ?version=<id> selects one.
# With no versions at all we fall back to the flat data/processed/*.json files
# (backward compatibility with runs made before versioning existed).


def _resolve_version(version: str | None) -> str | None:
    """The version id to serve: the requested one if it exists, else latest, else None."""
    ids = {v.get("id") for v in versioning.list_versions(PROCESSED)}
    if version and version in ids:
        return version
    return versioning.latest_version(PROCESSED)


def _artifact_path(name: str, version: str | None) -> Path:
    """Path to artifact ``name`` in the resolved version dir, else the flat file."""
    vid = _resolve_version(version)
    if vid is not None:
        p = PROCESSED / "versions" / vid / name
        if p.exists():
            return p
    return PROCESSED / name


def _unwrap(data, default):
    """Stage artifacts are envelopes ({schema_version, items, ...}); older flat
    files were bare lists. Serve the items either way."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else default


def _load_json(name: str, version: str | None, default):
    return _unwrap(_read_json(_artifact_path(name, version), default), default)


# --- run-centric observability (Studio v2) --------------------------------
# The 8-stage pipeline writes a per-stage artifact envelope + a ledger; these
# helpers surface run_id, per-stage drill-down (survived/killed + why), and one
# idea's full cross-stage lineage so the whole funnel is debuggable, not a
# black box. Every read is best-effort and degrades gracefully (missing artifact
# => impressions-only rows, flagged `degraded`).

from idea_factory.contract.artifacts import ARTIFACTS as _STAGE_FILE  # {stage: filename}
from idea_factory.contract.stage import STAGES as _FUNNEL_STAGES

# Where a stage-drill row's *fields* come from. enrich's own artifact is evidence
# (keyed by candidate), so its drilled entities are the ideas that entered it.
_DRILL_ENTITY_FILE = {
    "recall": "recall.json", "triage": "triage.json", "generate": "candidates.json",
    "rank": "ideas.json", "enrich": "ideas.json", "diligence": "verdicts.json",
    "portfolio": "screened.json",
}
# For killed items (absent from this stage's survivor artifact), pull fields from
# the previous stage's artifact where the id space matches.
_DRILL_PREV_FILE = {"triage": "recall.json", "rank": "candidates.json"}


def _entity_id(item: dict) -> str:
    return str(item.get("id") or item.get("idea_id") or "")


def _by_id(items: list) -> dict[str, dict]:
    return {_entity_id(i): i for i in items if isinstance(i, dict) and _entity_id(i)}


def _version_for_run(run_id: str) -> str | None:
    for v in versioning.list_versions(PROCESSED):
        if isinstance(v, dict) and v.get("run_id") == run_id:
            return v.get("id")
    return None


def _run_envelope(name: str, run_id: str) -> dict | None:
    """Full envelope of artifact ``name`` for a specific run (version snapshot,
    else the current flat file when it belongs to this run), else None."""
    vid = _version_for_run(run_id)
    if vid:
        env = _read_json(PROCESSED / "versions" / vid / name, None)
        if isinstance(env, dict):
            return env
    flat = _read_json(PROCESSED / name, None)
    if isinstance(flat, dict) and flat.get("run_id") == run_id:
        return flat
    return None


def _run_items(name: str, run_id: str) -> list:
    env = _run_envelope(name, run_id)
    return env.get("items", []) if isinstance(env, dict) else []


def list_runs_summary() -> list[dict]:
    """Every known run (version snapshots ∪ ledger), newest first."""
    versions = {v.get("run_id"): v for v in versioning.list_versions(PROCESSED) if isinstance(v, dict)}
    run_ids = set(ledger.list_runs(DATA_DIR)) | {r for r in versions if r}
    out = []
    for rid in run_ids:
        if not rid:
            continue
        v = versions.get(rid)
        out.append({
            "run_id": rid,
            "version_id": (v or {}).get("id"),
            "date": (v or {}).get("created_at") or rid.rsplit("-", 1)[0].split("-", 1)[-1],
            "week": (v or {}).get("week", ""),
            "has_artifacts": v is not None,
            "stages": ledger.stages_for_run(DATA_DIR, rid),
        })
    out.sort(key=lambda r: ledger._run_sort_key(r["run_id"]), reverse=True)
    return out


def run_funnel(run_id: str) -> dict:
    """One run's 8-stage funnel: entered→survived, killed, rate, kill reasons."""
    survival = ledger.channel_survival_rates(DATA_DIR, run_id=run_id)
    stages = []
    for st in _FUNNEL_STAGES:
        if st == "portfolio":
            continue  # portfolio logs no impressions; summarized from verdicts below
        s = survival.get(st)
        if not s:
            continue
        entered = s["survived"] + s["killed"]
        stages.append({
            "stage": st, "entered": entered, "survived": s["survived"],
            "killed": s["killed"], "rate": s["rate"],
            "kill_reasons": ledger.killed_by_breakdown(DATA_DIR, stage=st, run_id=run_id),
            "has_artifact": _run_envelope(_STAGE_FILE.get(st, ""), run_id) is not None,
        })
    # portfolio row derived from screened.json verdicts
    screened = _run_items("screened.json", run_id)
    vd = {"pursue": 0, "review": 0, "kill": 0}
    for e in screened:
        vd[e.get("verdict", "kill")] = vd.get(e.get("verdict", "kill"), 0) + 1
    survivors = vd["pursue"] + vd["review"]
    if screened:
        stages.append({
            "stage": "portfolio", "entered": len(screened), "survived": survivors,
            "killed": vd["kill"], "rate": round(survivors / len(screened), 4) if screened else 0.0,
            "kill_reasons": {}, "has_artifact": bool(screened),
        })
    return {
        "run_id": run_id,
        "week": (_run_envelope("ideas.json", run_id) or {}).get("week", ""),
        "date": (_run_envelope("ideas.json", run_id) or {}).get("date", ""),
        "stages": stages,
        "verdict_distribution": vd,
        "totals": {
            "entered": stages[0]["entered"] if stages else 0,
            "survived_final": survivors,
        },
    }


def stage_drill(run_id: str, stage: str) -> dict:
    """Items that passed/died at one stage, each with why (killed_by / gate)."""
    if stage not in _FUNNEL_STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    imps = [r for r in ledger.impressions_for_run(DATA_DIR, run_id) if r.get("stage") == stage]
    this_items = _by_id(_run_items(_DRILL_ENTITY_FILE.get(stage, ""), run_id))
    prev_items = _by_id(_run_items(_DRILL_PREV_FILE[stage], run_id)) if stage in _DRILL_PREV_FILE else {}
    # enrich gate (candidate_id -> {ready, missing}) from evidence.json extra
    gate = {}
    if stage == "enrich":
        env = _run_envelope("evidence.json", run_id)
        gate = (env or {}).get("gate", {}) if isinstance(env, dict) else {}
    degraded = not this_items and not prev_items
    items = []
    for r in imps:
        eid = r.get("entity_id", "")
        fields = this_items.get(eid) or prev_items.get(eid) or {}
        row = {
            "id": eid,
            "event": r.get("event"),
            "killed_by": r.get("killed_by"),
            "title": fields.get("title", ""),
            "source": fields.get("source", ""),
            "pain": fields.get("pain") or fields.get("pain_statement", ""),
        }
        if stage == "rank" and fields:
            row["alpha"] = fields.get("alpha")
            row["factors"] = fields.get("factors")
        if stage == "enrich":
            row["gate"] = gate.get(eid)
        items.append(row)
    survived = sum(1 for i in items if i["event"] == "survived")
    killed = sum(1 for i in items if i["event"] == "killed")
    return {
        "run_id": run_id, "stage": stage, "entered": len(items),
        "survived": survived, "killed": killed, "degraded": degraded, "items": items,
    }


def idea_lineage(run_id: str, idea_id: str) -> dict:
    """One idea's full cross-stage journey + its LLM traces (T6.2)."""
    candidate = _by_id(_run_items("candidates.json", run_id)).get(idea_id) \
        or _by_id(_run_items("ideas.json", run_id)).get(idea_id)
    signal_id = (candidate or {}).get("signal_id", "")
    signal = _by_id(_run_items("recall.json", run_id)).get(signal_id)

    imps = ledger.impressions_for_run(DATA_DIR, run_id)
    by_stage_entity = {(r.get("stage"), r.get("entity_id")): r for r in imps}

    def _imp(stage, eid):
        r = by_stage_entity.get((stage, eid))
        return {"survived": r.get("event") == "survived", "killed_by": r.get("killed_by")} if r else None

    ranked = _by_id(_run_items("ideas.json", run_id)).get(idea_id)
    evidence_items = [e for e in _run_items("evidence.json", run_id) if e.get("candidate_id") == idea_id]
    gate = ((_run_envelope("evidence.json", run_id) or {}).get("gate", {}) or {}).get(idea_id)
    verdict = _by_id(_run_items("verdicts.json", run_id)).get(idea_id) \
        or _by_id(_run_items("screened.json", run_id)).get(idea_id)

    traces = {}
    for tstage in ("critique", "diligence", "ask"):
        rows = [t for t in ledger.read_trace(DATA_DIR, run_id, tstage) if t.get("entity_id") == idea_id]
        if rows:
            traces[tstage] = rows
    labels = [v for v in ledger.read_jsonl(ledger.ledger_dir(DATA_DIR) / ledger.VERDICTS)
              if v.get("actor") == "founder" and v.get("candidate_id") == idea_id]

    return {
        "idea_id": idea_id, "run_id": run_id,
        "signal": signal,
        "triage": _imp("triage", signal_id) if signal_id else None,
        "candidate": candidate,
        "generate": _imp("generate", idea_id),
        "rank": {
            "factors": (ranked or {}).get("factors"), "alpha": (ranked or {}).get("alpha"),
            "decay": (ranked or {}).get("decay"), "coarse_selected": ranked is not None,
        } if candidate else None,
        "enrich": {"evidence": evidence_items, "gate": gate},
        "diligence": verdict,
        "traces": traces,
        "founder_labels": labels,
    }


def do_rerun_stage(body: dict) -> dict:
    """Destructive single-stage (or range) rerun via pipeline.run(only=/from/to).

    Overwrites data/processed/<artifact> and appends to the ledger, inheriting
    run_id from the upstream artifact on disk. Downstream artifacts go stale
    until they too are rerun -- the UI warns before calling this.
    """
    stage = body.get("stage")
    if stage and stage not in _FUNNEL_STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    today = _ref_date(body)
    r = pipeline.run(
        data_dir=DATA_DIR, output_dir=PROCESSED, today=today,
        only=stage, from_stage=body.get("from"), to_stage=body.get("to"),
        top_n=int(body.get("top_n", 15)), floor=body.get("floor"),
        generate_backend=body.get("generate_backend", "rule"),
        judge_backend=body.get("judge_backend", "none"),
        live=bool(body.get("live", False)),
    )
    return {
        "run_id": r.run_id, "week": r.week,
        "stages": [{"stage": s.stage, "entered": s.entered, "survived": s.survived,
                    "killed": s.killed} for s in r.stages],
    }


def overview(version: str | None = None) -> dict:
    ideas = _load_json("ideas.json", version, [])
    screened = _load_json("screened.json", version, [])
    verdicts = {"pursue": 0, "review": 0, "kill": 0}
    for e in screened:
        verdicts[e.get("verdict", "kill")] = verdicts.get(e.get("verdict", "kill"), 0) + 1
    return {
        "candidates": len(ideas),
        "evaluated": len(screened),
        "verdicts": verdicts,
        "factor_names": _factor_names(),
        "last_generate": _mtime_iso(_artifact_path("ideas.json", version)),
        "last_evaluate": _mtime_iso(_artifact_path("screened.json", version)),
        "judged_by_llm": any(e.get("judged_by") == "llm" for e in screened),
    }


# verdicts that survive the kill-gate (idea_eval); "kill" is excluded from top3
_SURVIVING_VERDICTS = ("pursue", "review")


def _one_liner(entry: dict) -> str:
    """浓缩现有字段成一句(不调 LLM):标题 + 最大赌注,压成单行、限长。"""
    title = (entry.get("title") or "").strip()
    risk = (entry.get("riskiest_assumption") or "").strip()
    line = f"{title} — 最大赌注:{risk}" if risk else title
    line = " ".join(line.split())  # collapse whitespace/newlines to one line
    return line[:200]


def top3() -> dict:
    """Read-only: today's top-3 non-killed ideas as a stable machine schema.

    screened.json is pre-sorted by idea_eval (_sort): verdict order
    (pursue < review < kill), then -eval_score, then idea_id — so the first
    three surviving entries are exactly the ranked top-3. No LLM, no writes.

    Reads the *latest* committed version's screened.json (falls back to the flat
    file when no versions exist).
    """
    path = _artifact_path("screened.json", None)
    screened = _unwrap(_read_json(path, []), [])
    survivors = [e for e in screened if e.get("verdict") in _SURVIVING_VERDICTS][:3]
    mtime = _mtime_iso(path)  # None if file missing
    ref = mtime or datetime.now().isoformat(timespec="seconds")
    top3_rows = []
    for rank, e in enumerate(survivors, start=1):
        top3_rows.append({
            "rank": rank,
            "idea_id": e.get("idea_id"),
            "title": e.get("title"),
            "one_liner": _one_liner(e),
            "score": e.get("eval_score"),
            "verdict": e.get("verdict"),
            "riskiest_assumption": e.get("riskiest_assumption"),
            "cheap_experiment": e.get("cheap_experiment"),
        })
    return {
        "date": ref[:10],
        "generated_at": ref,
        "count": len(top3_rows),
        "top3": top3_rows,
    }


def bets() -> dict:
    """Read-only: the latest run's bet_memos.json (agent-service-plan.md §2.2),
    verbatim -- the structured out-bound boundary artifact for oc's DMZ tool.
    Superset of ``top3()`` (full hypothesis/evidence/experiment, not a one-liner);
    ``top3`` stays as-is for existing consumers.
    """
    path = _artifact_path("bet_memos.json", None)
    envelope = _read_json(path, None)
    if not isinstance(envelope, dict) or "items" not in envelope:
        return {"run_id": "", "week": "", "date": "", "count": 0, "bets": []}
    return {
        "run_id": envelope.get("run_id", ""),
        "week": envelope.get("week", ""),
        "date": envelope.get("date", ""),
        "count": envelope.get("count", 0),
        "bets": envelope.get("items", []),
    }


def signals() -> list[dict]:
    raw = collect_all(DATA_DIR)
    return [s.to_dict() for s in normalize(raw)]


# --- founder profile (editable) ------------------------------------------
# Keys the kernel actually reads (factors._load_founder_reach + llm.render_founder_block).
# A PUT that would drop/break any of these is rejected 400 so an edit can never
# silently disable founder-fit scoring or the LLM founder block.


def read_founder_profile() -> dict:
    """Return config/founder.json as-is (incl. _labels/_version metadata)."""
    return _read_json(FOUNDER_PATH, {})


def validate_founder_profile(prof) -> str | None:
    """Return an error string if the profile is missing/malforms a required key, else None."""
    if not isinstance(prof, dict):
        return "profile must be a JSON object"
    identity = prof.get("identity")
    if not isinstance(identity, str) or not identity.strip():
        return "identity is required and must be a non-empty string"
    for key in ("reach_keywords_en", "reach_keywords_zh"):
        val = prof.get(key)
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            return f"{key} is required and must be a list of strings"
    # Other kernel-read keys: optional, but if present must be the right shape.
    for key in ("skills", "network", "language_region_edge", "hard_constraints", "anti_fit"):
        if key in prof and not isinstance(prof[key], list):
            return f"{key} must be a list"
    if "capital_rmb" in prof and not isinstance(prof["capital_rmb"], (int, float)):
        return "capital_rmb must be a number"
    return None


def write_founder_profile(prof: dict) -> dict:
    """Validate then atomically write config/founder.json (temp file + rename).

    Raises ValueError on validation failure (→ 400) without touching the file.
    """
    err = validate_founder_profile(prof)
    if err:
        raise ValueError(err)
    FOUNDER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = FOUNDER_PATH.parent / (FOUNDER_PATH.name + ".tmp")
    tmp.write_text(json.dumps(prof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(FOUNDER_PATH)  # atomic on same filesystem
    return {"ok": True}


def _ref_date(body: dict) -> date:
    d = body.get("date")
    try:
        return date.fromisoformat(d) if d else date.today()
    except (ValueError, TypeError):
        return date.today()


def do_generate(body: dict) -> dict:
    r = pipeline.run(
        data_dir=DATA_DIR,
        output_dir=PROCESSED,
        today=_ref_date(body),
        to_stage="rank",
        top_n=int(body.get("top_n", 15)),
        sources=body.get("sources") or None,
        generate_backend=body.get("backend", "rule"),
        live=bool(body.get("live", False)),
        use_state=bool(body.get("use_state", False)),
        persona_backend=body.get("persona_backend", "static"),
    )
    return {
        "raw_count": r.stage("recall").entered,
        "signal_count": r.stage("recall").survived,
        "deduped_count": r.stage("triage").survived,
        "candidate_count": r.stage("generate").survived,
    }


def do_inbox(body: dict) -> dict:
    """源② 持续录入:把一条灵感 append 到 data/raw/inbox.jsonl(零 token、本地)。"""
    import json as _json

    title = (body.get("title") or "").strip()
    if not title:
        return {"ok": False, "error": "empty"}
    rec = {
        "title": title,
        "pain": (body.get("pain") or title).strip(),
        "category": (body.get("category") or "ai-productivity").strip(),
        "observed_on": _ref_date(body).isoformat(),
    }
    path = DATA_DIR / "raw" / "inbox.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True}


def do_evaluate(body: dict) -> dict:
    r = pipeline.run(
        data_dir=DATA_DIR,
        output_dir=PROCESSED,
        today=_ref_date(body),
        from_stage="enrich",
        to_stage="portfolio",
        top_n=int(body.get("top_n", 20)),
        floor=float(body.get("floor", 0.25)),
        judge_backend=body.get("backend", "none"),
    )
    pf = r.stage("portfolio")
    return {
        "evaluated": pf.entered,
        "pursue": pf.extra.get("pursue", 0),
        "review": pf.extra.get("review", 0),
        "killed": pf.extra.get("killed", 0),
    }


# --- pipeline-v2: ledger (funnel / trace / founder-labels) -----------------
# Read-only views over data/ledger/*. The ledger is always-on (every run logs
# impressions/verdicts/traces); an empty ledger just means no run happened yet.


def ledger_funnel() -> dict:
    return eval_stats.funnel_report(DATA_DIR)


def ledger_verdicts() -> list[dict]:
    return ledger.read_jsonl(ledger.ledger_dir(DATA_DIR) / ledger.VERDICTS)


def ledger_outcomes() -> list[dict]:
    return ledger.read_outcomes(DATA_DIR)


def ledger_trace(run_id: str, stage: str) -> list[dict]:
    return ledger.read_trace(DATA_DIR, run_id, stage)


def _target_from_bet_memo(candidate_id: str, metric: str) -> float | None:
    """Best-effort target lookup for an outcome event that omits ``target``:
    the latest bet_memos.json's experiment.target for this candidate, only
    if its metric name matches (never guess a target for the wrong metric).
    """
    for b in _load_json("bet_memos.json", None, []):
        if b.get("bet_id") != candidate_id:
            continue
        exp = b.get("experiment") or {}
        if exp.get("metric") == metric and isinstance(exp.get("target"), (int, float)):
            return float(exp["target"])
    return None


def do_outcome(body: dict) -> dict:
    """POST /api/outcome -- the inbound boundary artifact (agent-service-plan.md
    §2.3, §0: "采集是 oc 的,消化是 idea-factory 的"). oc pushes a bet's
    real-world result here after it plays out on its own kanban; idea-factory
    never reads oc's board itself. Idempotent on ``event_id`` so oc's push
    workflow can retry freely without double-recording -- a resend is a 200
    no-op (``duplicate: true``), never a second ledger row.
    """
    candidate_id = (body.get("candidate_id") or "").strip()
    tested_at = (body.get("tested_at") or "").strip()
    metric = (body.get("metric") or "").strip()
    actual = body.get("actual")
    if not candidate_id or not tested_at or not metric or actual is None:
        raise ValueError("candidate_id, tested_at, metric and actual are required")
    event_id = (body.get("event_id") or "").strip()
    reported_by = (body.get("reported_by") or "oc").strip()

    if retro_outcomes.event_already_recorded(DATA_DIR, event_id):
        return {"ok": True, "duplicate": True, "event_id": event_id}

    target = body.get("target")
    if target is None:
        target = _target_from_bet_memo(candidate_id, metric)

    retro_outcomes.record_outcome(
        DATA_DIR, candidate_id, tested_at, metric, float(actual),
        target=target, horizon_days=body.get("horizon_days"),
        first_revenue=body.get("first_revenue"), lesson=(body.get("lesson") or ""),
        event_id=event_id, reported_by=reported_by,
    )
    return {"ok": True, "duplicate": False, "candidate_id": candidate_id, "target_used": target}


def do_label(body: dict) -> dict:
    """Founder UI action (star/kill/override) -> a label event in verdicts.jsonl.

    This is the highest-value data the system collects: every click here is a
    ground-truth signal, cheaper than a full retro cycle.
    """
    candidate_id = (body.get("candidate_id") or "").strip()
    action = (body.get("action") or "").strip()
    if not candidate_id or not action:
        raise ValueError("candidate_id and action are required")
    extra = {k: v for k, v in body.items() if k not in ("candidate_id", "action")}
    ledger.log_founder_action(DATA_DIR, candidate_id, action, **extra)
    return {"ok": True}


# --- rich founder feedback (case data for manual CC-driven optimization) ----
# Richer than the star/kill label: a set of problem-locating labels + a free
# text note, each record freezing the idea's FULL lineage snapshot so it stays
# self-contained for later hand analysis. Deliberately NOT wired into any
# optimization step -- accumulate now, the founder reads + aggregates in CC and
# writes the fix by hand. No frontend-triggered automation (by design).


def do_feedback(body: dict) -> dict:
    """Record one rich feedback event on an idea, with a frozen lineage snapshot.

    Body: ``{run_id, idea_id, labels: [str, ...], note: str}``. At least one of
    ``labels`` / ``note`` must be non-empty. ``labels`` are free strings (the UI
    offers a fixed vocabulary but the backend never hard-rejects unknown ones --
    forward-compat as the label set grows). The snapshot is whatever
    :func:`idea_lineage` reconstructs at write time, so the record survives a
    later artifact overwrite / version prune.
    """
    run_id = (body.get("run_id") or "").strip()
    idea_id = (body.get("idea_id") or "").strip()
    if not run_id or not idea_id:
        raise ValueError("run_id and idea_id are required")
    labels = body.get("labels") or []
    if not isinstance(labels, list):
        raise ValueError("labels must be a list")
    labels = [str(x).strip() for x in labels if str(x).strip()]
    note = (body.get("note") or "").strip()
    if not labels and not note:
        raise ValueError("at least one label or a note is required")

    lineage = idea_lineage(run_id, idea_id)  # the frozen, self-contained snapshot
    dil = lineage.get("diligence") or {}
    record = {
        "feedback_id": f"{run_id}:{idea_id}:{int(time.time() * 1000)}",
        "ts": ledger.now_iso(),
        "run_id": run_id,
        "idea_id": idea_id,
        "labels": labels,
        "note": note,
        # a few key fields lifted to the top for grep-friendly aggregation in CC;
        # the full detail lives under `lineage`.
        "system_verdict": dil.get("verdict"),
        "system_score": dil.get("eval_score"),
        "title": (lineage.get("candidate") or {}).get("title"),
        "lineage": lineage,
        "lineage_url": f"/#/run/{run_id}/idea/{idea_id}",
    }
    ledger.log_feedback(DATA_DIR, record)
    return {"ok": True, "feedback_id": record["feedback_id"]}


def feedback_for(run_id: str | None, idea_id: str | None) -> list[dict]:
    """Recent feedback, optionally filtered to one idea. Returns compact rows
    (no frozen lineage) so the UI list stays light; the full record is on disk.
    """
    rows = ledger.read_feedback(DATA_DIR)
    if idea_id:
        rows = [r for r in rows if r.get("idea_id") == idea_id]
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    return [
        {k: r.get(k) for k in ("feedback_id", "ts", "run_id", "idea_id", "labels",
                               "note", "system_verdict", "system_score", "title")}
        for r in rows
    ]


# Backends sensible for an interactive "try it now" UI call. "cc" is excluded on
# purpose: CC-handoff writes a job pack and pauses for a human to run Claude Code
# separately, which defeats the point of an instant what-if rerun.
_WHATIF_BACKENDS = ("mock", "router", "dify")


def do_whatif_judge(body: dict) -> dict:
    """Re-run ONLY the judge step for one candidate with edited fields.

    Scoped what-if (§6 M6 T6.4: judge stage only, not a generic per-stage rerun
    harness). Reads the live ideas.json but never writes to disk or the ledger
    -- the result is shown in the UI and discarded, exactly the "compare
    without committing" behavior the design calls for.
    """
    idea_id = body.get("idea_id", "")
    overrides = body.get("overrides") or {}
    backend_name = body.get("backend", "mock")
    if backend_name not in _WHATIF_BACKENDS:
        raise ValueError(f"backend must be one of {_WHATIF_BACKENDS} for an interactive what-if run")

    ideas = _load_json("ideas.json", None, [])
    idea = next((i for i in ideas if i.get("id") == idea_id), None)
    if idea is None:
        raise ValueError(f"idea {idea_id!r} not found in ideas.json")
    merged = {**idea, **overrides}

    ev = diligence_gate.evaluate_idea(merged, floor=diligence_gate.DEFAULT_FLOOR)
    llm = get_backend(backend_name)
    diligence_judge.judge_survivors([ev], {idea_id: merged}, llm, load_step_config("judge"))
    return {
        "idea_id": idea_id,
        "verdict": ev.verdict,
        "eval_score": ev.eval_score,
        "judged_by": ev.judged_by,
        "killer_objection": ev.killer_objection,
        "riskiest_assumption": ev.riskiest_assumption,
        "judge_reasons": ev.judge_reasons,
    }


# --- interactive ask (Studio v2 real-time follow-up) ----------------------
# Free-text Q&A grounded in ONE idea's full lineage. router (Tencent) for a real
# answer, mock fallback when router isn't configured. cc/dify excluded (cc pauses
# for a human = not real-time; dify unnecessary). Every turn is logged to the
# trace tree (stage="ask") so the follow-up dialogue is itself part of the record.
_ASK_BACKENDS = ("router", "mock")


def _idea_context(run_id: str, idea_id: str) -> str:
    """Compact, LLM-readable dump of an idea's cross-stage lineage for the ask prompt."""
    lin = idea_lineage(run_id, idea_id)
    sig = lin.get("signal") or {}
    cand = lin.get("candidate") or {}
    rank = lin.get("rank") or {}
    enr = lin.get("enrich") or {}
    dil = lin.get("diligence") or {}
    lines = [
        f"标题: {cand.get('title', '')}",
        f"痛点: {cand.get('pain', '')}",
        f"方案: {cand.get('solution', '')}",
        f"目标用户: {cand.get('target_user', '')}",
        f"来源信号: [{sig.get('source_name', sig.get('source', ''))}] {sig.get('title', '')}"
        f"（{sig.get('observed_on', '')}）原文: {sig.get('raw_text', '')[:400]}",
        f"生成侧因子分: {json.dumps(rank.get('factors') or {}, ensure_ascii=False)}  alpha={rank.get('alpha')}",
        f"证据门: {json.dumps(enr.get('gate') or {}, ensure_ascii=False)}  证据条数={len(enr.get('evidence') or [])}",
        f"裁决: {dil.get('verdict', '(未裁决)')}  分数={dil.get('eval_score')}  "
        f"最致命质疑={dil.get('killer_objection', '')}  最危险假设={dil.get('riskiest_assumption', '')}",
    ]
    reasons = dil.get("judge_reasons") or []
    if reasons:
        lines.append("裁决理由: " + " / ".join(r.get("claim", "") for r in reasons))
    return "\n".join(lines)


def do_ask(body: dict) -> dict:
    """Answer a founder's free-text question about one idea, grounded in its lineage.

    Persists the turn to traces/<run_id>/ask.jsonl (unlike whatif-judge, which is
    ephemeral) so the interactive dialogue becomes part of the debuggable record.
    """
    run_id = (body.get("run_id") or "").strip()
    idea_id = (body.get("idea_id") or "").strip()
    question = (body.get("question") or "").strip()
    backend_name = body.get("backend", "router")
    if not run_id or not idea_id or not question:
        raise ValueError("run_id, idea_id and question are required")
    if backend_name not in _ASK_BACKENDS:
        raise ValueError(f"backend must be one of {_ASK_BACKENDS} (cc/dify not allowed for interactive ask)")

    context = _idea_context(run_id, idea_id)
    config = load_step_config("ask")
    user = render_template(config.get("user_template", ""), {"idea_context": context, "question": question})
    req = build_request(idea_id, user, config)

    from idea_factory.runtime.llm import log_trace_batch

    used = backend_name
    try:
        resp = get_backend(backend_name).complete([req])[0]
        if not resp.ok and backend_name == "router":
            used = "mock"
            resp = get_backend("mock").complete([req])[0]
    except Exception:  # noqa: BLE001 — router misconfigured/unreachable → mock fallback
        used = "mock"
        resp = get_backend("mock").complete([req])[0]

    log_trace_batch(DATA_DIR, run_id, "ask", [req], {req.id: resp}, config.get("step", "ask"))
    return {
        "idea_id": idea_id, "run_id": run_id, "question": question,
        "answer": resp.text or ("(mock 后端无内容——配置 router 端点后可得真实回答)" if used == "mock" else ""),
        "backend": used, "usage": resp.usage, "latency_ms": resp.latency_ms,
        "ts": ledger.now_iso(),
    }


# --- HTTP handler ---------------------------------------------------------

_MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json", ".svg": "image/svg+xml",
    ".ico": "image/x-icon", ".png": "image/png", ".woff2": "font/woff2", ".map": "application/json",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "IdeaFactoryStudio/0.1"

    def log_message(self, *args):  # quieter logs
        pass

    # -- helpers --
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _cookie_token(self) -> str | None:
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == COOKIE:
                return v
        return None

    def _authed(self) -> bool:
        return (not _auth_enabled()) or _valid_token(self._cookie_token())

    def _bearer_ok(self) -> bool:
        """Machine auth (oc, not a browser) for /api/top3, /api/bets and
        POST /api/outcome: Authorization: Bearer <IDEA_TOP3_API_KEY>.

        Empty key => locked (never serves unauthed). Constant-time compare.
        """
        if not TOP3_API_KEY:
            return False
        auth = self.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return False
        return hmac.compare_digest(token.strip(), TOP3_API_KEY)

    # -- routing --
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self._api_get(path, parse_qs(parsed.query))
        return self._serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        body = self._body()
        if path == "/api/login":
            if not _auth_enabled() or body.get("password") == PASSWORD:
                token = _make_token()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header(
                    "Set-Cookie",
                    f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}",
                )
                payload = json.dumps({"ok": True}).encode()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            return self._json({"ok": False, "error": "wrong password"}, 401)
        if path == "/api/logout":
            self.send_response(200)
            self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; Max-Age=0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # machine endpoint: Bearer-key auth (oc pushes outcomes, no browser cookie)
        if path == "/api/outcome":
            if not self._bearer_ok():
                return self._json({"error": "unauthorized"}, 401)
            try:
                return self._json(do_outcome(body))
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        if not self._authed():
            return self._json({"error": "unauthorized"}, 401)
        try:
            if path == "/api/run/generate":
                return self._json(do_generate(body))
            if path == "/api/run/evaluate":
                return self._json(do_evaluate(body))
            if path == "/api/inbox":
                return self._json(do_inbox(body))
            if path == "/api/ledger/label":
                return self._json(do_label(body))
            if path == "/api/feedback":
                return self._json(do_feedback(body))
            if path == "/api/run/whatif-judge":
                return self._json(do_whatif_judge(body))
            if path == "/api/run/stage":
                return self._json(do_rerun_stage(body))
            if path == "/api/ask":
                return self._json(do_ask(body))
        except ValueError as exc:  # bad input (missing field, unknown idea/backend) → 400
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 — surface run errors to the UI
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({"error": "not found"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if not self._authed():
            return self._json({"error": "unauthorized"}, 401)
        body = self._body()
        try:
            if path == "/api/founder-profile":
                return self._json(write_founder_profile(body))
        except ValueError as exc:  # validation failure → bad request, file untouched
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001 — surface write errors to the UI
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({"error": "not found"}, 404)

    def _api_get(self, path, query=None):
        query = query or {}
        if path == "/api/me":
            return self._json({"auth": _auth_enabled(), "authed": self._authed()})
        # machine endpoints: Bearer-key auth, separate from the browser cookie session
        if path == "/api/top3":
            if not self._bearer_ok():
                return self._json({"error": "unauthorized"}, 401)
            try:
                return self._json(top3())
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        if path == "/api/bets":
            if not self._bearer_ok():
                return self._json({"error": "unauthorized"}, 401)
            try:
                return self._json(bets())
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        if not self._authed():
            return self._json({"error": "unauthorized"}, 401)
        version = (query.get("version") or [None])[0]
        try:
            # run-centric observability (prefix-matched): /api/runs, /api/run/<id>[/stage|idea/<x>]
            if path == "/api/runs":
                return self._json(list_runs_summary())
            parts = [unquote(p) for p in path.strip("/").split("/")]  # api/run/<id>/...
            if len(parts) >= 3 and parts[1] == "run":
                run_id = parts[2]
                if len(parts) == 3:
                    return self._json(run_funnel(run_id))
                if len(parts) == 5 and parts[3] == "stage":
                    return self._json(stage_drill(run_id, parts[4]))
                if len(parts) == 5 and parts[3] == "idea":
                    return self._json(idea_lineage(run_id, parts[4]))
            if path == "/api/versions":
                return self._json(versioning.list_versions(PROCESSED))
            if path == "/api/overview":
                return self._json(overview(version))
            if path == "/api/ideas":
                return self._json(_load_json("ideas.json", version, []))
            if path == "/api/decisions":
                return self._json(_load_json("screened.json", version, []))
            if path == "/api/signals":
                return self._json(signals())
            if path == "/api/founder-profile":
                return self._json(read_founder_profile())
            if path == "/api/ledger/funnel":
                return self._json(ledger_funnel())
            if path == "/api/ledger/verdicts":
                return self._json(ledger_verdicts())
            if path == "/api/ledger/outcomes":
                return self._json(ledger_outcomes())
            if path == "/api/feedback":
                return self._json(feedback_for(
                    (query.get("run_id") or [None])[0],
                    (query.get("idea_id") or [None])[0],
                ))
            if path == "/api/ledger/trace":
                run_id = (query.get("run_id") or [""])[0]
                stage = (query.get("stage") or [""])[0]
                if not run_id or not stage:
                    return self._json({"error": "run_id and stage query params are required"}, 400)
                return self._json(ledger_trace(run_id, stage))
        except Exception as exc:  # noqa: BLE001
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({"error": "not found"}, 404)

    def _serve_static(self, path):
        rel = path.lstrip("/") or "index.html"
        target = (WEB_DIST / rel).resolve()
        # SPA fallback + path-traversal guard
        if not str(target).startswith(str(WEB_DIST.resolve())) or not target.is_file():
            target = WEB_DIST / "index.html"
        if not target.is_file():
            return self._json({"error": "frontend not built — run npm run build in studio/web"}, 503)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    auth = "ON" if _auth_enabled() else "OFF (set STUDIO_PASSWORD!)"
    print(f"Idea Factory Studio on http://{HOST}:{PORT}  | auth: {auth} | dist: {WEB_DIST}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
