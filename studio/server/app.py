"""Idea Factory Studio — control-panel backend (stdlib only, zero deps).

A thin web layer over the idea-factory kernel:
  * serves the built React/TS frontend (studio/web/dist) as a SPA
  * exposes a small JSON API that reads the kernel's outputs and triggers runs
  * gates everything behind a single shared password (nginx does NOT auth)

It imports the kernel in-process (idea_gen / idea_eval) — no subprocess, no DB,
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
from urllib.parse import parse_qs, urlparse

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
from idea_core import ledger, versioning  # noqa: E402
from idea_core.llm import get_backend, load_dotenv, load_step_config  # noqa: E402
from idea_gen.collect import collect_all  # noqa: E402
from idea_gen.normalize import normalize  # noqa: E402
from idea_gen.pipeline import run_pipeline  # noqa: E402
from idea_eval import evaluate  # noqa: E402
from idea_eval import stats as eval_stats  # noqa: E402
from idea_eval.pipeline import run_evaluation  # noqa: E402

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
    from idea_core.factors import FACTORS

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


def _load_json(name: str, version: str | None, default):
    return _read_json(_artifact_path(name, version), default)


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
    screened = _read_json(path, [])
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
    r = run_pipeline(
        data_dir=DATA_DIR,
        output_dir=PROCESSED,
        today=_ref_date(body),
        top_n=int(body.get("top_n", 15)),
        sources=body.get("sources") or None,
        gen_backend=body.get("backend", "rule"),
        live=bool(body.get("live", False)),
        use_state=bool(body.get("use_state", False)),
        persona_backend=body.get("persona_backend", "static"),
    )
    return {
        "raw_count": r.raw_count,
        "signal_count": r.signal_count,
        "deduped_count": r.deduped_count,
        "candidate_count": r.candidate_count,
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
    r = run_evaluation(
        input_path=PROCESSED / "ideas.json",
        output_dir=PROCESSED,
        today=_ref_date(body),
        top_n=int(body.get("top_n", 20)),
        floor=float(body.get("floor", 0.25)),
        judge_backend=body.get("backend", "none"),
    )
    return {"evaluated": r.evaluated, "pursue": r.pursue, "review": r.review, "killed": r.killed}


# --- pipeline-v2: ledger (funnel / trace / founder-labels) -----------------
# Read-only views over data/ledger/* (docs/design/pipeline-v2-plan.md §6 M6).
# Populated only when a run used idea_gen's --use-triage or idea_eval's
# --require-evidence; an empty ledger just means those opt-in flags haven't
# been exercised yet, not an error.


def ledger_funnel() -> dict:
    return eval_stats.funnel_report(DATA_DIR)


def ledger_verdicts() -> list[dict]:
    return ledger.read_jsonl(ledger.ledger_dir(DATA_DIR) / ledger.VERDICTS)


def ledger_outcomes() -> list[dict]:
    return ledger.read_outcomes(DATA_DIR)


def ledger_trace(run_id: str, stage: str) -> list[dict]:
    return ledger.read_trace(DATA_DIR, run_id, stage)


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

    ev = evaluate.evaluate_idea(merged, floor=evaluate.DEFAULT_FLOOR)
    llm = get_backend(backend_name)
    evaluate.judge_survivors([ev], {idea_id: merged}, llm, load_step_config("judge"))
    return {
        "idea_id": idea_id,
        "verdict": ev.verdict,
        "eval_score": ev.eval_score,
        "judged_by": ev.judged_by,
        "killer_objection": ev.killer_objection,
        "riskiest_assumption": ev.riskiest_assumption,
        "judge_reasons": ev.judge_reasons,
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
        """Machine auth for /api/top3: Authorization: Bearer <IDEA_TOP3_API_KEY>.

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
            if path == "/api/run/whatif-judge":
                return self._json(do_whatif_judge(body))
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
        # machine endpoint: Bearer-key auth, separate from the browser cookie session
        if path == "/api/top3":
            if not self._bearer_ok():
                return self._json({"error": "unauthorized"}, 401)
            try:
                return self._json(top3())
            except Exception as exc:  # noqa: BLE001
                return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        if not self._authed():
            return self._json({"error": "unauthorized"}, 401)
        version = (query.get("version") or [None])[0]
        try:
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
