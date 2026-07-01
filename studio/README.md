# Idea Factory Studio

A web control panel for the idea-factory engine — front/back separated, TS frontend.

- **Frontend** (`web/`): Vite + React + **TypeScript** SPA. A dense "quant terminal"
  dashboard: Overview (pipeline + stats), Ideas (ranked candidates + factor bars),
  Decisions (verdicts, killer objections, RAT experiments), Signals, Run pipeline.
- **Backend** (`server/app.py`): **stdlib-only** Python (zero deps). Imports the
  kernel in-process, serves the built SPA + a small JSON API, gated by a single
  shared password (nginx does not auth). Listens on `127.0.0.1:3010`.

## Develop

```bash
# backend (terminal 1)
STUDIO_PASSWORD=dev python3 studio/server/app.py

# frontend dev server with hot reload (terminal 2) — proxies /api to :3010
cd studio/web && npm install && npm run dev   # http://localhost:5174
```

## Build + run (single origin)

```bash
cd studio/web && npm install && npm run build   # -> studio/web/dist
STUDIO_PASSWORD='a-strong-password' python3 studio/server/app.py   # serves dist + /api on :3010
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/api/me` | auth status |
| POST | `/api/login` `{password}` | sets signed-cookie session |
| POST | `/api/logout` | clears session |
| GET  | `/api/overview` | counts, verdicts, factor names, last-run times |
| GET  | `/api/ideas` | ranked candidates (`ideas.json`) |
| GET  | `/api/decisions` | screened evaluations (`screened.json`) |
| GET  | `/api/signals` | normalized 3-source signals |
| POST | `/api/run/generate` `{backend,sources,top_n}` | run idea-gen |
| POST | `/api/run/evaluate` `{backend,floor,top_n}` | run idea-eval |
| GET  | `/api/top3` | **machine endpoint** — today's top-3 non-killed ideas, stable schema (read-only) |

`/api/top3` is for downstream agents, **not** the browser cookie session: it
authenticates with `Authorization: Bearer <IDEA_TOP3_API_KEY>` and returns
`{date, generated_at, count, top3:[{rank, idea_id, title, one_liner, score,
verdict, riskiest_assumption, cheap_experiment}]}`. It only reads
`data/processed/screened.json` (no generate, no writes); missing/empty file =>
`200 {"count":0,"top3":[]}`. If `IDEA_TOP3_API_KEY` is unset the endpoint is
locked (401 for everyone). Example:

```bash
curl -H "Authorization: Bearer $IDEA_TOP3_API_KEY" http://127.0.0.1:3010/api/top3
```

Env: `STUDIO_PASSWORD` (required for the UI/cookie auth), `STUDIO_PORT` (default
3010), `STUDIO_SECRET` (cookie HMAC; defaults to the password),
`IDEA_TOP3_API_KEY` (Bearer key for `/api/top3`; empty => endpoint locked). Live
LLM runs use the kernel's `IDEA_LLM_*` / `OPENAI_*` (auto-loaded from repo
`.env`). See `.env.example`.

## Deploy on studio.enjoyapier.cloud

The domain currently points to Hermes Studio (127.0.0.1:3001). This panel uses
**3010** so it doesn't clash. `claude-user` is **not** passwordless-sudo and not
in the docker group — the steps below need an operator with sudo.

```bash
# 1. build the frontend
cd studio/web && npm ci && npm run build

# 2. set the panel password (gitignored .env, alongside IDEA_LLM_*)
echo "STUDIO_PASSWORD=<a-strong-password>" >> .env

# 3. run the backend as a service
sudo cp studio/deploy/idea-factory-studio.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now idea-factory-studio
curl -sI http://127.0.0.1:3010/        # sanity: should respond

# 4. point nginx at it (back up the old Hermes Studio conf first)
sudo cp /etc/nginx/sites-available/oc-studio{,.hermes.bak}
sudo cp studio/deploy/studio.enjoyapier.cloud.conf /etc/nginx/sites-available/oc-studio
sudo ln -sf /etc/nginx/sites-available/oc-studio /etc/nginx/sites-enabled/oc-studio
sudo nginx -t && sudo systemctl reload nginx

# 5. (optional) stop the old Hermes Studio container — it's profile-gated, safe to stop
sudo docker compose --profile studio stop hermes-studio   # in ../one-creator
```

Rollback: `sudo cp /etc/nginx/sites-available/oc-studio.hermes.bak /etc/nginx/sites-available/oc-studio && sudo nginx -t && sudo systemctl reload nginx`.

TLS: the existing `enjoyapier.cloud` cert already covers the `studio` SAN — no certbot needed.
