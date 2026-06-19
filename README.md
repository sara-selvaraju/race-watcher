# race-watcher

Personal race-day dashboard for the Flemington meeting on **Saturday 20 June 2026**.

- Backend: FastAPI + SQLAlchemy + Alembic + Pydantic v2 (Python 3.12, uv).
- Odds: a research adapter that calls any chat model via OpenRouter (with `:online` web search) to look up current decimal WIN odds from public web sources on demand via `POST /api/v1/admin/refresh-odds`. Model is configurable (`OPENROUTER_MODEL`). Append-only snapshots, threshold-based movement detection, dedupe. A direct-Anthropic adapter is wired alongside as an alternative.
- Worker: separate process; re-runs heuristic predictions every 30 min so ratings stay current. No live polling.
- Frontend: Next.js (App Router) + TypeScript + Tailwind + React Query.
- Database: Postgres.
- Deploy: Railway (three services + Postgres plugin).

> Heuristic ratings are not a trained model and not financial advice. Gambling Help 1800 858 858.

## Layout

```
backend/                    FastAPI app (api/) + worker (worker/main.py) sharing one domain
  src/race_watcher/
    api/v1/                 routers + schemas (validate + delegate only)
    core/                   config, logging
    db/                     SQLAlchemy models, session, base
    domain/                 ports (RaceCardSource / OddsSource / PredictionEngine), domain models
    repositories/           data access
    services/               business logic
    adapters/               seed.py, betfair.py, heuristic.py
    worker/main.py          5-min poller entrypoint
  alembic/                  migrations
  seed/flemington.json      race card seed for 2026-06-20
  tests/                    pytest

frontend/                   Next.js client (API consumer only)
  src/
    app/                    App Router pages
    components/             presentational + container split
    lib/api/                generated typed client (from OpenAPI)
```

## Local dev

```bash
# backend
cd backend
uv sync
cp ../.env.example .env
uv run alembic upgrade head
uv run uvicorn race_watcher.api.app:app --reload    # api on :8000
uv run python -m race_watcher.worker.main           # worker in a second terminal

# frontend
cd ../frontend
npm install
npm run gen:api            # regenerate the typed client from the live API
npm run dev                # web on :3000
```

## Railway

Three services off this repo + Postgres plugin:

| Service | Root | Start | Healthcheck |
|---|---|---|---|
| api    | `backend`  | `uvicorn race_watcher.api.app:app --host 0.0.0.0 --port $PORT` | `/healthz` |
| worker | `backend`  | `python -m race_watcher.worker.main` | — |
| web    | `frontend` | `npm run start` | `/` |

`alembic upgrade head` runs as a release step on the `api` service. Env vars come from `.env.example`. The `api` service must expose its URL to the `web` service as `NEXT_PUBLIC_API_BASE_URL` at build time.
