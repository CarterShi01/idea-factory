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
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal stdlib .env loader: KEY=VALUE lines, does not override existing env.

    Lets the CLIs pick up credentials from a gitignored .env without a dependency.
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

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
    # Observability (null on the offline/mock path -> cost-gradient stays measurable
    # only when a real backend runs, without touching the zero-token default path).
    usage: dict | None = None     # {prompt_tokens, completion_tokens, total_tokens}
    latency_ms: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LLMResponse":
        known = {k: d[k] for k in ("id", "text", "data", "ok", "error", "usage", "latency_ms") if k in d}
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


# --- observability: usage / cost -----------------------------------------
# Field naming follows the OpenInference semantic conventions
# (llm.token_count.prompt/completion, llm.cost.total) but kept snake_case here.


def _norm_usage(usage: dict | None) -> dict | None:
    """Normalize an OpenAI-compatible ``usage`` block to our 3-field shape."""
    if not isinstance(usage, dict):
        return None
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    tt = usage.get("total_tokens")
    if pt is None and ct is None and tt is None:
        return None
    if tt is None and (pt is not None or ct is not None):
        tt = (pt or 0) + (ct or 0)
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}


def _dify_usage(meta: dict | None) -> dict | None:
    """Map a Dify workflow ``data`` block to our usage shape (best-effort)."""
    if not isinstance(meta, dict):
        return None
    tt = meta.get("total_tokens")
    if tt is None:
        return None
    return {"prompt_tokens": None, "completion_tokens": None, "total_tokens": tt}


_PRICES_CACHE: dict | None = None


def _load_prices() -> dict:
    """config/llm/prices.json (founder-filled, like founder.json). Missing -> {}.

    Cached per process; best-effort (a bad/absent file just means cost stays null).
    """
    global _PRICES_CACHE
    if _PRICES_CACHE is None:
        default_dir = Path(os.environ.get("IDEA_LLM_CONFIG_DIR", "config/llm"))
        try:
            _PRICES_CACHE = json.loads((default_dir / "prices.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _PRICES_CACHE = {}
    return _PRICES_CACHE if isinstance(_PRICES_CACHE, dict) else {}


def price_for(model: str) -> dict | None:
    """Per-model price ``{input_per_1k, output_per_1k}`` or None if unpriced."""
    p = _load_prices().get(model)
    return p if isinstance(p, dict) else None


def log_trace_batch(
    trace_data_dir,
    trace_run_id: str | None,
    stage: str,
    requests: list,
    responses: dict,
    prompt_version: str,
) -> None:
    """Log every request/response in a batch to the ledger trace, with usage/cost/
    latency. Shared by all LLM steps (diligence critique/judge, generate, persona,
    ask). No-op unless both ``trace_data_dir``/``trace_run_id`` are given -- so the
    offline default path (no real backend, no complete()) writes nothing.
    """
    if trace_data_dir is None or trace_run_id is None:
        return
    from idea_factory.runtime import ledger

    for req in requests:
        r = responses.get(req.id)
        model = (r.model if r and hasattr(r, "model") else None) or req.model or ""
        usage = r.usage if r else None
        ledger.log_trace(
            trace_data_dir, trace_run_id, stage, req.id,
            prompt_version=prompt_version,
            request={"system": req.system, "user": req.user},
            response=(r.to_dict() if r else {}),
            model=model,
            usage=usage,
            cost=cost_of(model, usage) if r else None,
            latency_ms=(r.latency_ms if r else None),
        )


def cost_of(model: str, usage: dict | None) -> float | None:
    """¥ cost of one call from its usage + the price table; None when unknown.

    Computed at log time so historical trace rows stay self-describing even if
    prices change later. Missing model / missing tokens -> None (not 0).
    """
    price = price_for(model)
    if not price or not isinstance(usage, dict):
        return None
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    inp = price.get("input_per_1k", 0.0)
    outp = price.get("output_per_1k", 0.0)
    if pt is None and ct is None:
        tt = usage.get("total_tokens")
        if tt is None:
            return None
        return round(tt / 1000 * max(inp, outp), 6)  # no split -> upper-bound estimate
    return round((pt or 0) / 1000 * inp + (ct or 0) / 1000 * outp, 6)


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
        # Minimum gap between sequential calls — LKEAP rate-limits bursts with 400s.
        self.min_interval = float(os.environ.get("IDEA_LLM_MIN_INTERVAL", "1.0"))

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
        return data["choices"][0]["message"]["content"], data.get("usage")

    def complete(self, requests: list[LLMRequest], retries: int = 2) -> list[LLMResponse]:
        out: list[LLMResponse] = []
        for i, r in enumerate(requests):
            if i:
                time.sleep(self.min_interval)  # throttle to respect the rate limit
            model = r.model or self.model
            last = ""
            for attempt in range(retries + 1):
                try:
                    t0 = time.perf_counter()
                    text, usage = self._chat(r.system, r.user, r.temperature, model)
                    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                    data = extract_json(text) if r.schema else None
                    out.append(LLMResponse(
                        id=r.id, text=text, data=data, ok=True,
                        usage=_norm_usage(usage), latency_ms=latency_ms,
                    ))
                    last = ""
                    break
                except Exception as exc:  # noqa: BLE001 -- one bad call shouldn't kill the batch
                    last = f"{type(exc).__name__}: {exc}"
                    if attempt < retries:
                        time.sleep(self.min_interval * (attempt + 1))  # backoff for transient 4xx / rate limits
            else:
                out.append(LLMResponse(id=r.id, ok=False, error=last))
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


class DifyBackend:
    """Calls a Dify *workflow* app published from idea-factory's own flows.

    The flow definitions (DSL) live in this repo under ``dify/flows/*.yml`` and are
    the git source of truth (GitOps); Dify is the editor + runtime. Each pipeline
    step (generate / critique / judge) maps to its own Dify workflow app + API key.

    Flow I/O contract (keep the Dify Start/End node variables matching this, or
    override via env): the Start node takes text inputs ``system`` and ``user``
    (plus optional ``schema``); the End node outputs one variable ``result`` (text).
    The prompt itself lives *inside* the Dify flow — idea-factory only ships the
    system/user content and (optionally) the JSON schema for extraction.

    Config (env): ``IDEA_DIFY_BASE_URL`` (default ``http://127.0.0.1:8080/v1``),
    ``IDEA_DIFY_<STEP>_API_KEY`` then ``IDEA_DIFY_API_KEY`` (per-app key from Dify's
    *API Access* panel), ``IDEA_DIFY_OUTPUT_KEY`` (default ``result``),
    ``IDEA_DIFY_USER``, ``IDEA_DIFY_MIN_INTERVAL``. Stdlib only, provider-neutral.
    """

    name = "dify"

    def __init__(
        self,
        step: str = "generate",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        self.step = step
        self.base_url = (
            base_url or os.environ.get("IDEA_DIFY_BASE_URL") or "http://127.0.0.1:8080/v1"
        ).rstrip("/")
        self.api_key = (
            api_key
            or os.environ.get(f"IDEA_DIFY_{step.upper()}_API_KEY")
            or os.environ.get("IDEA_DIFY_API_KEY")
            or ""
        )
        self.timeout = timeout
        self.user = os.environ.get("IDEA_DIFY_USER", "idea-factory")
        self.output_key = os.environ.get("IDEA_DIFY_OUTPUT_KEY", "result")
        self.min_interval = float(os.environ.get("IDEA_DIFY_MIN_INTERVAL", "0.5"))

    def _run(self, req: LLMRequest) -> str:
        url = f"{self.base_url}/workflows/run"
        # ⑤: the strategy/system prompt lives *inside* the Dify flow (visually
        # editable); we only ship the user content (which already carries the
        # founder block, see build_request) + optional schema. The flow's Start
        # node therefore only needs ``user`` (+ ``schema``).
        inputs = {"user": req.user}
        if req.schema:
            inputs["schema"] = json.dumps(req.schema, ensure_ascii=False)
        payload = {"inputs": inputs, "response_mode": "blocking", "user": self.user}
        http_req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:  # noqa: S310 (configured URL)
            body = json.loads(resp.read().decode("utf-8"))
        meta = body.get("data") or {}
        outputs = meta.get("outputs") or {}
        if self.output_key in outputs:
            val = outputs[self.output_key]
        elif outputs:
            val = next(iter(outputs.values()))
        else:
            val = ""
        text = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        return text, meta

    def complete(self, requests: list[LLMRequest], retries: int = 2) -> list[LLMResponse]:
        if not self.api_key:
            err = f"dify backend: set IDEA_DIFY_{self.step.upper()}_API_KEY or IDEA_DIFY_API_KEY"
            return [LLMResponse(id=r.id, ok=False, error=err) for r in requests]
        out: list[LLMResponse] = []
        for i, r in enumerate(requests):
            if i:
                time.sleep(self.min_interval)  # gentle throttle (small machine / single worker)
            last = ""
            for attempt in range(retries + 1):
                try:
                    t0 = time.perf_counter()
                    text, meta = self._run(r)
                    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                    data = extract_json(text) if r.schema else None
                    out.append(LLMResponse(
                        id=r.id, text=text, data=data, ok=True,
                        usage=_dify_usage(meta), latency_ms=latency_ms,
                    ))
                    last = ""
                    break
                except Exception as exc:  # noqa: BLE001 -- one bad call shouldn't kill the batch
                    last = f"{type(exc).__name__}: {exc}"
                    if attempt < retries:
                        time.sleep(self.min_interval * (attempt + 1))
            else:
                out.append(LLMResponse(id=r.id, ok=False, error=last))
        return out


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
    if name == "dify":
        return DifyBackend(**kwargs)
    raise ValueError(f"unknown LLM backend: {name!r}")


def backend_for_step(
    name: str,
    step: str,
    today_iso: str,
    job_dir: str | Path = "data/llm_jobs",
) -> "LLMBackend":
    """Build a backend for one named LLM step (generate/critique/judge/...).

    CC-handoff gets a dated, *step-scoped* job name so each step becomes its own
    manual fulfilment pack (critique-<date>, judge-<date>, ...); Dify resolves
    its per-step app/key (prompt lives in the flow, config/llm is the mirror).
    """
    if name == "cc":
        return get_backend("cc", job_dir=job_dir, job_name=f"{step}-{today_iso}")
    if name == "dify":
        return get_backend("dify", step=step)
    return get_backend(name)


def load_step_config(step: str, config_dir: str | Path | None = None) -> dict:
    """Load the prompt/schema/params config for a step (e.g. 'generate', 'judge')."""
    default_dir = Path(os.environ.get("IDEA_LLM_CONFIG_DIR", "config/llm"))
    path = Path(config_dir or default_dir) / f"{step}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_founder_profile(path: str | Path | None = None) -> dict | None:
    """Load the founder profile (config/founder.json) if present, else None.

    The profile describes *who will actually build & sell the idea* (skills,
    capital, network, language/region edge, hard constraints). Optional: absence
    just means the prompts run founder-agnostic (back-compat).
    """
    from idea_factory.runtime.config import founder_path

    p = Path(path) if path else founder_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def render_founder_block(profile: dict | None) -> str:
    """Format the founder profile as a prompt section injected into every step.

    Grounds generation/critique/judge in the real operator: a one-person company
    must be able to *build it* (capital/skills), *reach the first users* (network),
    and lean on a *moat* (the Mongolian/Inner-Mongolia language edge). Returns ""
    when there is no profile so prompts stay unchanged.
    """
    if not profile:
        return ""
    lines: list[str] = [
        "# 创始人画像（务必据此判断『这条 idea 适不适合由这位创始人来做』——执行者就是他本人）",
        f"- 身份：{profile.get('identity', '')}",
    ]
    cap = profile.get("capital_rmb")
    if cap is not None:
        lines.append(f"- 启动资金：约 {cap} 人民币。{profile.get('capital_note', '')}")
    for key, header in (
        ("skills", "技能"),
        ("network", "可低成本触达的人脉/渠道"),
        ("language_region_edge", "语言/地域独占优势（护城河）"),
        ("hard_constraints", "硬约束"),
        ("anti_fit", "明显不适合他的方向"),
    ):
        items = profile.get(key) or []
        if items:
            lines.append(f"- {header}：")
            lines.extend(f"  · {it}" for it in items)
    lines.append(
        "判断规则：优先有现成渠道/技能/语言地域优势、且 6 万资金内一人能启动并早期收钱的方向；"
        "对需要烧钱买量、养团队、长期不赚钱、或他既无技能也无渠道的方向要明确扣分或质疑。"
    )
    return "\n".join(lines)


# Cached so we read config/founder.json at most once per process.
_FOUNDER_CACHE: dict | None = None
_FOUNDER_LOADED = False


def _founder_block_cached() -> str:
    global _FOUNDER_CACHE, _FOUNDER_LOADED
    if not _FOUNDER_LOADED:
        _FOUNDER_CACHE = load_founder_profile()
        _FOUNDER_LOADED = True
    return render_founder_block(_FOUNDER_CACHE)


def build_request(item_id: str, user: str, config: dict) -> LLMRequest:
    """Turn a rendered user prompt + a step config into an LLMRequest.

    ``config['model_env']`` (optional) — name of an env var to read the per-step
    model from (e.g. ``IDEA_LLM_JUDGE_MODEL``). Lets generate vs critique vs
    judge run on *different* models (anti self-enhancement) without editing
    config or code. Resolution order: env[model_env] → config.model → backend
    default.

    The founder profile (config/founder.json) is prepended to the system prompt of
    every step so generation, critique, and judging all reason about whether *this
    specific founder* can build, reach, and defend the idea. Steps can opt out with
    ``config['skip_founder'] = true``.
    """
    model = config.get("model")
    env_name = config.get("model_env")
    if env_name:
        env_model = os.environ.get(env_name)
        if env_model:
            model = env_model

    system = config.get("system", "")
    if not config.get("skip_founder"):
        block = _founder_block_cached()
        if block:
            # ⑤ (docs/design/dify-prompt-authoring.md §3.2): the founder profile
            # rides in the USER message (it is data from config/founder.json), not
            # the system prompt — so it reaches the Dify flow, whose LLM node embeds
            # its own visually-editable system prompt and is NOT sent ours. Router /
            # mock still see the identical founder + data content.
            user = f"{block}\n\n{user}" if user else block

    return LLMRequest(
        id=item_id,
        system=system,
        user=user,
        schema=config.get("schema"),
        temperature=config.get("temperature", 0.2),
        model=model,
    )


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # tolerate missing placeholders
        return ""


def render_template(template: str, fields: dict) -> str:
    """Render a ``str.format``-style template, leaving missing keys blank."""
    return template.format_map(_SafeDict(fields))
