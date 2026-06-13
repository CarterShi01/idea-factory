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
from urllib.parse import urlparse

# --- locate repo root and import the kernel -------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = REPO_ROOT / "studio" / "web" / "dist"
DATA_DIR = REPO_ROOT / "data"
PROCESSED = DATA_DIR / "processed"

import sys

sys.path.insert(0, str(REPO_ROOT / "src"))
from idea_core.llm import load_dotenv  # noqa: E402
from idea_gen.collect import collect_all  # noqa: E402
from idea_gen.normalize import normalize  # noqa: E402
from idea_gen.pipeline import run_pipeline  # noqa: E402
from idea_eval.pipeline import run_evaluation  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

HOST = os.environ.get("STUDIO_HOST", "127.0.0.1")
PORT = int(os.environ.get("STUDIO_PORT", "3010"))
PASSWORD = os.environ.get("STUDIO_PASSWORD", "")  # empty => auth disabled (dev)
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


def overview() -> dict:
    ideas = _read_json(PROCESSED / "ideas.json", [])
    screened = _read_json(PROCESSED / "screened.json", [])
    verdicts = {"pursue": 0, "review": 0, "kill": 0}
    for e in screened:
        verdicts[e.get("verdict", "kill")] = verdicts.get(e.get("verdict", "kill"), 0) + 1
    return {
        "candidates": len(ideas),
        "evaluated": len(screened),
        "verdicts": verdicts,
        "factor_names": _factor_names(),
        "last_generate": _mtime_iso(PROCESSED / "ideas.json"),
        "last_evaluate": _mtime_iso(PROCESSED / "screened.json"),
        "judged_by_llm": any(e.get("judged_by") == "llm" for e in screened),
    }


def signals() -> list[dict]:
    raw = collect_all(DATA_DIR)
    return [s.to_dict() for s in normalize(raw)]


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

    # -- routing --
    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self._api_get(path)
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
        except Exception as exc:  # noqa: BLE001 — surface run errors to the UI
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({"error": "not found"}, 404)

    def _api_get(self, path):
        if path == "/api/me":
            return self._json({"auth": _auth_enabled(), "authed": self._authed()})
        if not self._authed():
            return self._json({"error": "unauthorized"}, 401)
        try:
            if path == "/api/overview":
                return self._json(overview())
            if path == "/api/ideas":
                return self._json(_read_json(PROCESSED / "ideas.json", []))
            if path == "/api/decisions":
                return self._json(_read_json(PROCESSED / "screened.json", []))
            if path == "/api/signals":
                return self._json(signals())
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
