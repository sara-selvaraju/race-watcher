# Deploying to Railway

Race Watcher runs as one Railway project with four parts: a Postgres database and three services
built from this repo (`api`, `worker`, `web`).

## 1. Postgres

Add the **Postgres** database to the project. Railway provides `DATABASE_URL`; reference it from
the `api` and `worker` services.

## 2. `api` service

- **Source:** this repo, root directory `backend`
- **Start command:** `uv run alembic upgrade head && uv run uvicorn race_watcher.api.app:app --host 0.0.0.0 --port $PORT`
  (database migrations run on every start)
- **Healthcheck path:** `/healthz`
- **Public domain:** yes; the website needs it
- **Variables:**

| Variable | Example |
|---|---|
| `DATABASE_URL` | reference to Postgres |
| `ADMIN_TOKEN` | a long random string, e.g. from `openssl rand -hex 24` |
| `OPENROUTER_API_KEY` | your OpenRouter key |
| `RACE_DATE` | `2026-10-31` |
| `RACE_DATE_END` | `2026-11-07` (leave out for a single day) |
| `SEED_FILE_PATH` | `seed/flemington-carnival-2026.json` |
| `TZ` | `Australia/Melbourne` |

  Everything else has a sensible default; see `.env.example`.

## 3. `worker` service

- **Source:** this repo, root directory `backend`
- **Start command:** `uv run python -m race_watcher.worker.main`
- **No public domain, no healthcheck.**
- **Variables:** the same as `api`, apart from `ADMIN_TOKEN`, which it doesn't use. Optionally
  set `POLL_INTERVAL_SECONDS` to fetch odds more or less often (default 900).

On start, the worker loads the race card if nothing is loaded for the race days yet. It then runs
two jobs: odds every 15 minutes during race hours, and ratings plus notes every 10 minutes.

## 4. `web` service

- **Source:** this repo, root directory `frontend`
- **Build command:** `npm install && npm run build`
- **Start command:** `npm run start`
- **Healthcheck path:** `/`
- **Variables:** `NEXT_PUBLIC_API_BASE_URL=https://<your api domain>`. This is baked in when the
  site is built, so set it before the first build, and redeploy `web` if it changes.

## Deploying changes

If the services are connected to GitHub with the root directories above, pushing deploys them.

You can also deploy straight from a local copy with the Railway CLI. Run these from the repo
root; `--path-as-root` is needed because the services build from a subfolder:

```bash
railway up backend  --path-as-root -s api    --detach
railway up backend  --path-as-root -s worker --detach
railway up frontend --path-as-root -s web    --detach
```

## Checking it's working

1. `https://<api domain>/healthz` returns `{"status": "ok"}`.
2. `https://<api domain>/api/v1/meetings` lists the race days and races.
3. The worker's logs show `worker.boot`, then `worker.odds` every 15 minutes
   (`poller.outside_window` outside race hours) and `worker.summaries` every 10.
4. The website shows the race days, read-only. To refresh, open it with `?admin` on the end of
   the address, enter the admin token once (the browser remembers it), then press **Refresh**.
   It runs odds, tips, ratings, field and notes for that day.

## Loading a new race card

1. Update the JSON in `backend/seed/` and, if the dates change, `RACE_DATE` / `RACE_DATE_END`.
2. Redeploy `api` and `worker`.
3. Load it:

   ```bash
   curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" https://<api domain>/api/v1/admin/ingest
   ```
