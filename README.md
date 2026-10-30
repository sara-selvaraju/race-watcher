# Race Watcher

A race-day dashboard for Australian thoroughbred racing. For every race it shows the field, live
odds and how they're moving, a rating for each runner, the top three picks with sourced
reasoning, and a short plain-English note on why those runners are the picks.

It's built to follow the races you care about for a day or a few days, not to run all year.
Pick a meeting, a carnival or a handful of races, load their cards, and watch them come
together: prices firming and drifting, picks settling, notes updating. When the last race has
run, the worker goes quiet and costs nothing until you point it at the next set of races.

It's currently set up for the 2026 Flemington Spring Carnival: Derby Day, Melbourne Cup Day,
Oaks Day and Stakes Day.

![Race Watcher showing Derby Day: next to jump, the race days, and the top picks with a race note](docs/screenshot.png)

> **Not betting advice.** Ratings come from a simple, explainable heuristic, not a trained model,
> and the odds and tips are gathered by an LLM doing web searches, which can be wrong or stale.
> If gambling is causing you harm, call Gambling Help on 1800 858 858.

## What it does

- **Race days and races.** One tab per race day (or per track, when several tracks race on the
  same day), and every race on the card, run or not.
- **Next to jump.** A live countdown to the next race, in Melbourne time and in yours.
- **Odds.** Current win prices for every runner, fetched every 15 minutes while a race day is on,
  kept as a history so you can see who's firming and who's drifting. Big moves (10% or more) show
  up in a movement feed.
- **Ratings.** A win chance and rating for each runner, recomputed as prices change.
- **Top picks.** Three picks per race from web research, with numbered links to the sources.
- **Race notes.** A short summary of why the picks are the picks, written from the prices, form
  and ratings in the database and nothing else.
- **Refresh (admin only).** One button per day that runs the whole pipeline on demand: odds,
  tips, ratings, missing runners, then notes. Viewers get a read-only page; the button only
  appears in a browser that has the admin token. To enter it, open the site with `?admin` on the
  end of the address (e.g. `https://your-site/?admin`).

## How it works

```mermaid
flowchart LR
  seed[Race card JSON] -->|ingest| db[(Postgres)]
  or[OpenRouter<br/>LLM + web search] -->|odds, tips, missing runners| db
  worker[Worker<br/>timed jobs] --> or
  worker -->|ratings, notes| db
  api[API<br/>FastAPI] --> db
  web[Website<br/>Next.js] -->|reads| api
  web -->|Refresh, with admin token| api
  api --> or
```

There are three services and a database:

- **API** (`backend/`, FastAPI). Serves the race days, races, runners, prices, picks and notes.
  Also has `/admin` endpoints that do the expensive work (calling an LLM); those need an admin
  token.
- **Worker** (`backend/src/race_watcher/worker/main.py`). A small always-on process with two timed
  jobs:
  - **Odds, every 15 minutes.** Only does anything while a race day is "on": from 2 hours before
    its first race to 15 minutes after its last. It asks for prices for the races still to run,
    stores each one as a new snapshot (never overwriting the old ones), and records an alert when
    a price moves 10% or more.
  - **Ratings and notes, every 10 minutes.** Re-rates the runners using the latest prices, then
    rewrites the note for any race whose prices, picks or field have changed. Races that haven't
    changed are skipped, so this costs nothing when the market is quiet.

  Outside racing hours, and once every race has run, the worker sits idle.
- **Website** (`frontend/`, Next.js). Reads from the API and refreshes as new data lands.
- **Postgres** holds everything.

### Where the data comes from

| Data | Source |
|---|---|
| Race card: races, fields, barriers, weights, jockeys, trainers, form figures | A JSON file in `backend/seed/`, put together from published final fields before each race day |
| Live odds | An LLM with web search via [OpenRouter](https://openrouter.ai) (default `anthropic/claude-sonnet-4.5` with `:online`) |
| Top picks and their sources | [Perplexity Sonar](https://openrouter.ai/perplexity/sonar-pro) via OpenRouter |
| Runners missing from the card | Perplexity Sonar; these are marked "unverified" on the site |
| Race notes | The same LLM without web search, given only facts from the database |

There's no clean, free, official feed for Australian race fields and odds, which is why the card
comes from a JSON file and the odds come from LLM web search. The code is written so these can be
swapped: a Betfair Exchange adapter is included as a more reliable odds source if you have an
account.

### How runners are rated

`backend/src/race_watcher/adapters/heuristic.py` scores each runner from:

1. **The market.** The price turned into an implied chance (a $4.00 runner is about 25%). Live
   prices are used once there are any, otherwise the preview price from the card.
2. **Tipster consensus,** if the card has one for that runner.
3. **A small wet-track bump** for runners whose form notes mention a wet track.

The scores are then scaled so a race's chances add up to 100%. Because the market dominates, the
ratings mostly reflect what the prices say; they're there to make the numbers comparable at a
glance, not to beat the market.

### Design choices worth knowing

- **Ports and adapters.** The core code talks to three interfaces (`RaceCardSource`,
  `OddsSource`, `PredictionEngine` in `domain/ports.py`), and each source is an adapter behind one
  of them. Swapping where odds come from is a config change, not a rewrite.
- **The API is the contract.** The frontend's TypeScript client is generated from the API's
  OpenAPI schema, so a backend change that breaks the frontend fails the type check.
- **Prices are append-only.** Every price fetched is a new row, so price history, sparklines and
  movement alerts all come from the same data.
- **Notes can't make things up (as far as possible).** The note writer gets a fixed list of facts
  (picks, prices, form spelled out most-recent-first, ratings) and is told to use nothing else, to
  never infer class or distance from form figures, and to say so when the facts are thin.

## Running it locally

You'll need Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, and Postgres (or Docker
for it).

```bash
# 1. Database
docker run -d --name race-pg -e POSTGRES_USER=race -e POSTGRES_PASSWORD=race \
  -e POSTGRES_DB=race_watcher -p 5432:5432 postgres:16

# 2. Settings
cp .env.example .env          # then add your OPENROUTER_API_KEY
cp .env backend/.env

# 3. API (terminal 1)
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn race_watcher.api.app:app --reload          # http://localhost:8000/docs

# 4. Worker (terminal 2): loads the race card on first start
cd backend
uv run python -m race_watcher.worker.main

# 5. Website (terminal 3)
cd frontend
npm install
npm run dev                                               # http://localhost:3000
```

Locally, with `ADMIN_TOKEN` unset, the admin endpoints are open. Open
http://localhost:3000/?admin and type anything as the token to get the Refresh button.

Without an OpenRouter key the site still works from the race card alone: you'll see fields, form
and preview prices, but no live odds, picks or notes.

### Tests and checks

```bash
cd backend && uv run pytest              # backend tests (SQLite in memory, no network)
cd frontend && npx tsc --noEmit          # frontend type check
```

If you change an API response, regenerate the frontend client:

```bash
cd backend && uv run python -c "import json; from race_watcher.api.app import app; \
  open('openapi.json','w').write(json.dumps(app.openapi(), indent=2)+'\n')"
cd ../frontend && npm run gen:api:local
```

## Setting up a race day

1. Write the card as JSON in `backend/seed/` (see `flemington-carnival-2026.json` for the
   format). One entry per meeting; a meeting is one track on one date. Races without a final
   field yet can have `"runners": []`, and a day with no card yet can have `"races": []`.
2. Point the app at it with `SEED_FILE_PATH`, and set `RACE_DATE` (and `RACE_DATE_END` for a
   multi-day carnival).
3. Load it with `POST /api/v1/admin/ingest`. Loading again is safe: it updates races and
   runners in place.

## Configuration

All settings are environment variables; `.env.example` lists them with comments. The main ones:

| Variable | What it does |
|---|---|
| `DATABASE_URL` | Postgres connection |
| `RACE_DATE`, `RACE_DATE_END` | First and last race day shown (inclusive) |
| `SEED_FILE_PATH` | The race card JSON |
| `OPENROUTER_API_KEY` | Needed for odds, picks and notes |
| `OPENROUTER_MODEL` | Model for odds and notes |
| `OPENROUTER_RESEARCH_MODEL` | Model for picks and missing runners |
| `ADMIN_TOKEN` | Secret for the `/admin` endpoints and the Refresh button. **Set this in production** |
| `POLL_INTERVAL_SECONDS` | How often the worker fetches odds during a race day (default 900, 15 minutes) |
| `MOVEMENT_THRESHOLD_PCT` | Price move that counts as an alert (default 10) |
| `NEXT_PUBLIC_API_BASE_URL` | The API's address, for the website (baked in at build time) |

### What it costs

Odds fetching is one web-search LLM call per race day every 15 minutes, for about 7–8 hours, so
around 30 calls a day. Notes only call the LLM when a race's facts change. A full Refresh makes
one call for odds plus one research call per race for picks and another for missing runners.
Check your usage on OpenRouter; raising `POLL_INTERVAL_SECONDS` is the main way to spend less.

## Deploying

It runs on [Railway](https://railway.app) as three services (api, worker, web) plus Postgres.
See [DEPLOY.md](DEPLOY.md).

## Project layout

```
backend/
  src/race_watcher/
    api/            FastAPI app, routers and response schemas
    adapters/       seed file, OpenRouter, heuristic, Betfair, mock odds
    domain/         ports (interfaces) and plain domain models
    services/       ingest, odds polling, ratings, picks, field expansion, race notes
    repositories/   database queries
    db/             SQLAlchemy models
    worker/         the timed jobs
  alembic/          database migrations
  seed/             race cards
  tests/
frontend/
  src/
    app/            the page
    components/     race nav, next to jump, picks, field, movement feed, refresh bar
    lib/            API client (generated), time and track helpers
```

## Licence

MIT. See [LICENSE](LICENSE).
