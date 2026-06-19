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
  - `ODDS_SOURCE=betfair` (or `mock` until you wire creds)
  - `PREDICTION_ENGINE=heuristic`
  - `BETFAIR_APP_KEY`, `BETFAIR_USERNAME`, `BETFAIR_PASSWORD` (and optional `BETFAIR_CERT_PATH`, `BETFAIR_CERT_KEY_PATH`)
- Once deployed, hit `POST /api/v1/admin/ingest` once to load the seed → DB, then `POST /api/v1/admin/predict` to seed the heuristic predictions. The worker keeps both fresh.

## 3) `worker` service (5-min poller)

- Repo: this repo
- Root directory: `backend`
- Builder: Nixpacks
- Start command (override): `uv run python -m race_watcher.worker.main`
- No public domain, no healthcheck.
- Same env as `api` (it shares the DB + adapter config).
- Tunables:
  - `POLL_INTERVAL_SECONDS=300`
  - `MOVEMENT_THRESHOLD_PCT=10`
  - `RACE_WINDOW_OPEN_MIN_BEFORE=120`
  - `RACE_WINDOW_CLOSE_MIN_AFTER=15`

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
