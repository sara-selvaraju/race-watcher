# race-watcher

Personal race-day dashboard for the Flemington meeting on **Saturday 20 June 2026**.

- Backend: FastAPI + SQLAlchemy + Alembic + Pydantic v2 (Python 3.12, uv).
- One **Refresh card** button on the dashboard runs four LLM-backed admin endpoints in sequence (frontend orchestrates so each ~15–90s step is visible):
  1. **Field** (`POST /api/v1/admin/expand-field`) — research the official runner list per race and backfill missing jockey/trainer/barrier.
  2. **Odds** (`POST /api/v1/admin/refresh-odds`) — fetch current decimal WIN odds for every runner via OpenRouter with `:online` web search; append-only snapshots, threshold-based movement detection, dedupe.
  3. **Research** (`POST /api/v1/admin/refresh-tips`) — Perplexity Sonar produces top-3 picks per race with cited reasoning; numbered citations are post-processed into inline clickable links.
  4. **Ratings** (`POST /api/v1/admin/predict`) — recompute the heuristic win-prob for every runner.
- Adapters: OpenRouter for odds (model configurable via `OPENROUTER_MODEL`); Perplexity Sonar via OpenRouter for research (`OPENROUTER_RESEARCH_MODEL`); seed JSON for the initial race card. A direct-Anthropic odds adapter is wired as an alternative.
- Worker: separate process; re-runs heuristic ratings every 30 min so they stay current as odds snapshots roll in. No live polling.
- Frontend: Next.js (App Router) + TypeScript + Tailwind + React Query. Japanese-bento light theme.
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
    services/               poller, predictions, expand_field, top_picks, ingest, movement
    adapters/               seed, openrouter, claude_research, betfair, heuristic, mock_odds
    worker/main.py          periodic heuristic re-rating
  alembic/                  migrations
  seed/flemington.json      race card seed for 2026-06-20
  tests/                    pytest

frontend/                   Next.js client (API consumer only)
  src/
    app/                    App Router pages
    components/             Header, RefreshBar, RaceNav, TopPicksBox, FieldBox, MovementFeed
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
