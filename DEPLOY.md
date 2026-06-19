# Railway deploy

You'll create **three services** in one Railway project plus a Postgres plugin.

## 1) Postgres

Add the **Postgres** plugin. Railway exposes `DATABASE_URL` to the project.

## 2) `api` service (FastAPI)

- Repo: this repo
- Root directory: `backend`
- Builder: Nixpacks (auto-detected)
- Start command (override): `uv run alembic upgrade head && uv run uvicorn race_watcher.api.app:app --host 0.0.0.0 --port $PORT`
- Healthcheck path: `/healthz`
- Required env:
  - `DATABASE_URL` — reference Postgres plugin
  - `RACE_DATE=2026-06-20`
  - `TZ=Australia/Melbourne`
  - `RACE_CARD_SOURCE=seed`
  - `SEED_FILE_PATH=seed/flemington.json`
  - `ODDS_SOURCE=openrouter` (default — uses any model via OpenRouter + web search)
  - `PREDICTION_ENGINE=heuristic`
  - `OPENROUTER_API_KEY` (required for `ODDS_SOURCE=openrouter`)
  - `OPENROUTER_MODEL=anthropic/claude-sonnet-4.5` (default — change to any OpenRouter-supported model)
  - `OPENROUTER_WEB_SEARCH=true` (default — appends `:online` so the model can actually look up odds)
  - For the alternative direct-Anthropic path: `ODDS_SOURCE=claude` + `ANTHROPIC_API_KEY` + `CLAUDE_RESEARCH_MODEL=claude-sonnet-4-6`
- On-demand odds refresh: `POST /api/v1/admin/refresh-odds`. There is no longer a 5-min poll — call this when you want fresh prices.
- After first deploy: `POST /api/v1/admin/ingest` once to load the seed → DB, then `POST /api/v1/admin/predict` to seed heuristic predictions.

## 3) `worker` service (background)

- Repo: this repo
- Root directory: `backend`
- Builder: Nixpacks
- Start command (override): `uv run python -m race_watcher.worker.main`
- No public domain, no healthcheck.
- Same env as `api`.
- Polling is **disabled**. The worker only re-runs heuristic predictions every 30 min so ratings stay current as snapshots roll in. Odds refresh is now on-demand via `POST /api/v1/admin/refresh-odds`.
- Tunables (only used when `/admin/refresh-odds` is called):
  - `MOVEMENT_THRESHOLD_PCT=10`
  - `RACE_WINDOW_OPEN_MIN_BEFORE=120`, `RACE_WINDOW_CLOSE_MIN_AFTER=15` (the refresh endpoint bypasses the window)

## 4) `web` service (Next.js)

- Repo: this repo
- Root directory: `frontend`
- Builder: Nixpacks
- Build command: `npm install && npm run build`
- Start command: `npm run start`
- Healthcheck path: `/`
- Required env at **build time**:
  - `NEXT_PUBLIC_API_BASE_URL=https://<api-service-public-url>` — Next.js bakes `NEXT_PUBLIC_*` into the client at build, so set this *before* the build runs.

## Confirming the pipeline

1. `api` /healthz → 200
2. `POST /api/v1/admin/ingest` → meeting loaded
3. `worker` logs `poller.fetched` and `poller.done`
4. `GET /api/v1/meeting/today` returns the meeting with current prices and a price history per runner
5. `GET /api/v1/alerts` returns moves once thresholds trip
6. `web` shows the dashboard, R1–R9 nav, runner table, movement feed
