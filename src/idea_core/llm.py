"""idea_core.llm -- the provider-neutral, batch-first LLM abstraction.

The whole point (see docs/design/llm-abstraction.md): every LLM step is a pure
function over a **prepared batch** -- ``list[LLMRequest] -> list[LLMResponse]``.
*Who* fills the responses is a pluggable backend:

* ``RouterBackend``     -- calls Tencent LKEAP (OpenAI-compatible) now, automatically.
* ``CCHandoffBackend``  -- writes a self-contained request pack to disk and lets a
  human fulfill the whole batch in ONE Claude Code session later (token-thrifty).
* ``MockBackend``       -- deterministic, offline; for stage-0 and tests.

Because the request/response *contract* is identical across backends, switching
from "run it on Tencent now" to "have CC do it by hand later" is a config flip,
not a rewrite. stdlib only.

The Tencent client is adapted from one-creator's ``brain-mcp/think_tools.py``
(``router_chat`` + ``_extract_json``).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

# --- L2: the unchanging contract -----------------------------------------


@dataclass
class LLMRequest:
    id: str                       # links back to a candidate/idea; used to match responses
    system: str
    user: str                     # fully rendered, self-contained user content
    schema: dict | None = None    # optional JSON schema the response must satisfy
    temperature: float = 0.2
    model: str | None = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LLMRequest":
        known = {k: d[k] for k in ("id", "system", "user", "schema", "temperature", "model", "meta") if k in d}
        return cls(**known)


@dataclass
class LLMResponse:
    id: str
    text: str = ""
    data: dict | None = None      # parsed JSON when a schema/extractable output is present
    ok: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LLMResponse":
        known = {k: d[k] for k in ("id", "text", "data", "ok", "error") if k in d}
        return cls(**known)


@runtime_checkable
class LLMBackend(Protocol):
    name: str

    def complete(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        ...


# --- helpers --------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort parse of a JSON object out of an LLM reply (tolerant)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _JSON_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


# --- L1: backends ---------------------------------------------------------


class PendingHandoff(Exception):
    """Raised by CCHandoffBackend when a request pack is waiting for a human/CC.

    Carries the path of the request pack so the caller can tell the user exactly
    what to run.
    """

    def __init__(self, request_path: Path, count: int):
        self.request_path = request_path
        self.count = count
        super().__init__(
            f"{count} LLM requests written to {request_path}. "
            f"Run them in Claude Code, then re-run this command to continue."
        )


class MockBackend:
    """Offline, deterministic backend. Default responder echoes a stub."""

    name = "mock"

    def __init__(self, responder: Callable[[LLMRequest], LLMResponse] | None = None):
        self._responder = responder

    def complete(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        out: list[LLMResponse] = []
        for r in requests:
            if self._responder:
                out.append(self._responder(r))
            else:
                out.append(LLMResponse(id=r.id, text="", data={}, ok=True))
        return out


class RouterBackend:
    """Calls an OpenAI-compatible endpoint (Tencent LKEAP via one-creator's router,
    or the LKEAP endpoint directly). Provider-neutral, env-configured, stdlib only.
    """

    name = "router"

    # Refuse expensive engines so a token-thrifty step can never hit a metered pool.
    _BLOCKED = ("anthropic", "claude", "api.anthropic.com")

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 60,
    ):
        # Prefer idea-factory's own env vars, then fall back to the standard
        # OPENAI_* vars so an ambient OpenAI-compatible endpoint (e.g. Tencent
        # LKEAP) works out of the box, then the local router default.
        # base_url should include the version path (".../v1", ".../plan/v3", …),
        # per the OpenAI convention; we append "/chat/completions".
        self.base_url = (
            base_url
            or os.environ.get("IDEA_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "http://cli-proxy-api:8317/v1"
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.environ.get("IDEA_LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or "local-router-key"
        )
        self.model = (
            model
            or os.environ.get("IDEA_LLM_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or "tc-code"
        )
        self.timeout = timeout

    def _guard(self, model: str) -> None:
        low = (model or "").lower()
        if any(b in low for b in self._BLOCKED) or "anthropic" in self.base_url.lower():
            raise RuntimeError(f"engine guard: refusing expensive engine '{model}' @ {self.base_url}")

    def _chat(self, system: str, user: str, temperature: float, model: str) -> str:
        self._guard(model)
        url = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (trusted, configured URL)
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]

    def complete(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        out: list[LLMResponse] = []
        for r in requests:
            model = r.model or self.model
            try:
                text = self._chat(r.system, r.user, r.temperature, model)
                data = extract_json(text) if r.schema else None
                out.append(LLMResponse(id=r.id, text=text, data=data, ok=True))
            except Exception as exc:  # noqa: BLE001 -- one bad call shouldn't kill the batch
                out.append(LLMResponse(id=r.id, ok=False, error=f"{type(exc).__name__}: {exc}"))
        return out


class CCHandoffBackend:
    """Token-thrifty mode: don't call any API. Materialize the whole batch as a
    self-contained request pack for a human to fulfill in ONE Claude Code session.

    Two-phase, idempotent:
      * No response file yet  -> write ``<job>.request.jsonl``, raise PendingHandoff.
      * Response file present -> read ``<job>.response.jsonl``, match by id, return.
    """

    name = "cc"

    def __init__(self, job_dir: str | Path = "data/llm_jobs", job_name: str = "job"):
        self.job_dir = Path(job_dir)
        self.job_name = job_name

    @property
    def request_path(self) -> Path:
        return self.job_dir / f"{self.job_name}.request.jsonl"

    @property
    def response_path(self) -> Path:
        return self.job_dir / f"{self.job_name}.response.jsonl"

    def complete(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        if self.response_path.exists():
            by_id: dict[str, LLMResponse] = {}
            for line in self.response_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    resp = LLMResponse.from_dict(json.loads(line))
                    by_id[resp.id] = resp
            return [
                by_id.get(r.id, LLMResponse(id=r.id, ok=False, error="missing in response pack"))
                for r in requests
            ]

        # First pass: write the pack and stop.
        self.job_dir.mkdir(parents=True, exist_ok=True)
        with self.request_path.open("w", encoding="utf-8") as fh:
            for r in requests:
                fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        raise PendingHandoff(self.request_path, len(requests))


# --- factory + config -----------------------------------------------------


def get_backend(name: str | None = None, **kwargs) -> LLMBackend:
    """Resolve a backend by name (defaults to env ``IDEA_LLM_BACKEND`` or 'mock')."""
    name = (name or os.environ.get("IDEA_LLM_BACKEND", "mock")).lower()
    if name == "router":
        return RouterBackend(**kwargs)
    if name == "cc":
        return CCHandoffBackend(**kwargs)
    if name == "mock":
        return MockBackend(**kwargs)
    raise ValueError(f"unknown LLM backend: {name!r}")


_CONFIG_DIR = Path(os.environ.get("IDEA_LLM_CONFIG_DIR", "config/llm"))


def load_step_config(step: str, config_dir: str | Path | None = None) -> dict:
    """Load the prompt/schema/params config for a step (e.g. 'generate', 'judge')."""
    path = Path(config_dir or _CONFIG_DIR) / f"{step}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_request(item_id: str, user: str, config: dict) -> LLMRequest:
    """Turn a rendered user prompt + a step config into an LLMRequest."""
    return LLMRequest(
        id=item_id,
        system=config.get("system", ""),
        user=user,
        schema=config.get("schema"),
        temperature=config.get("temperature", 0.2),
        model=config.get("model"),
    )


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # tolerate missing placeholders
        return ""


def render_template(template: str, fields: dict) -> str:
    """Render a ``str.format``-style template, leaving missing keys blank."""
    return template.format_map(_SafeDict(fields))
