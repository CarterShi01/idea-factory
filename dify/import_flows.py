#!/usr/bin/env python3
"""Import idea-factory's Dify flow DSLs (dify/flows/*.yml) into a running Dify
instance — the GitOps "deploy" step: git is the source of truth, this re-imports
it so the live instance matches the repo.

Stdlib only. Best-effort against Dify's console import API; verify the endpoints
against your Dify version (this targets the v1.x console API:
``/console/api/login`` + ``/console/api/apps/imports`` [+ ``/confirm``]).

Usage:
    DIFY_CONSOLE_URL=http://127.0.0.1:8080 \
    DIFY_EMAIL=you@example.com DIFY_PASSWORD=... \
    python3 dify/import_flows.py [flows/idea-gen.yml ...]

    # or skip login with a pre-obtained console token:
    DIFY_CONSOLE_TOKEN=... python3 dify/import_flows.py

No args → imports every dify/flows/*.yml. Exits non-zero if any import fails
(so CI goes red on drift).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("DIFY_CONSOLE_URL", "http://127.0.0.1:8080").rstrip("/")
FLOWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flows")


def _post(path: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (configured URL)
        return json.loads(resp.read().decode("utf-8"))


def get_token() -> str:
    tok = os.environ.get("DIFY_CONSOLE_TOKEN")
    if tok:
        return tok
    email, pw = os.environ.get("DIFY_EMAIL"), os.environ.get("DIFY_PASSWORD")
    if not (email and pw):
        sys.exit("set DIFY_CONSOLE_TOKEN, or DIFY_EMAIL + DIFY_PASSWORD")
    data = _post("/console/api/login", {"email": email, "password": pw, "remember_me": True})
    # v1.x returns {"result":"success","data":{"access_token":...}} (older: {"data": "<token>"})
    d = data.get("data")
    token = d.get("access_token") if isinstance(d, dict) else d
    if not token:
        sys.exit(f"login: no access_token in response: {data}")
    return token


def import_one(path: str, token: str) -> bool:
    yaml_content = open(path, encoding="utf-8").read()
    try:
        res = _post(
            "/console/api/apps/imports",
            {"mode": "yaml-content", "yaml_content": yaml_content},
            token,
        )
    except urllib.error.HTTPError as e:
        print(f"  ✗ {os.path.basename(path)}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}")
        return False
    status = res.get("status")
    import_id = res.get("id")
    app_id = res.get("app_id")
    # Some versions stage the import and require an explicit confirm.
    if status == "pending" and import_id:
        try:
            res = _post(f"/console/api/apps/imports/{import_id}/confirm", {}, token)
            status, app_id = res.get("status", status), res.get("app_id", app_id)
        except urllib.error.HTTPError as e:
            print(f"  ✗ {os.path.basename(path)} confirm: HTTP {e.code}")
            return False
    ok = status in ("completed", "success") or bool(app_id)
    print(f"  {'✓' if ok else '✗'} {os.path.basename(path)} → status={status} app_id={app_id}")
    return ok


def main(argv: list[str]) -> int:
    files = argv or sorted(glob.glob(os.path.join(FLOWS_DIR, "*.yml")))
    if not files:
        print(f"no flow DSLs in {FLOWS_DIR} (export from Dify first); nothing to import.")
        return 0
    token = get_token()
    print(f"importing {len(files)} flow(s) into {BASE} ...")
    ok = all(import_one(f, token) for f in files)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
