# Deploying TeamLedger to Railway

Quick guide for deploying the TeamLedger stack to Railway.app.

## Prerequisites
- Railway account (the free $5 trial credit is enough for a small instance)
- This repository connected to a Railway project

## One-time setup

1. Create a new Railway project → "+ New Project" → "Deploy from GitHub repo".
2. Pick the TeamLedger repo.
3. Railway auto-detects the root-level `Dockerfile` and starts building.

## Required environment variables

Set these in **Variables** tab of the service:

| Variable | Required | Example |
|----------|----------|---------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:pass@host:5432/dbname` (see "Database" below) |
| `SECRET_KEY` | Yes | `openssl rand -hex 32` |
| `APP_ENV` | Yes | `production` |
| `ALLOWED_ORIGINS` | Recommended | `https://your-app.up.railway.app` |
| `STORAGE_BACKEND` | Optional | `local` (default) |
| `STORAGE_ROOT` | Optional | `/app/storage` (default) |

> **Do NOT** set `PORT` manually. Railway injects `$PORT` for the app.

## Database (Postgres)

1. In the Railway project, click "+ New" → "Database" → "PostgreSQL".
2. After it spins up, click the Postgres service → "Variables" → copy `DATABASE_URL`.
3. Paste it into the TeamLedger service's `DATABASE_URL` variable.
4. Redeploy the TeamLedger service — migrations run automatically on each boot.

> The default SQLite fallback (file under `/app/storage`) is **ephemeral**: every
> redeploy wipes the database. For anything beyond local exploration, attach a
> Postgres instance.

## How it builds

- Builder: **Dockerfile** (auto-detected at repo root)
- dockerfilePath: `Dockerfile`
- Healthcheck: `GET /healthz`
- On every boot: `alembic upgrade head` then `uvicorn app.main:app`

## Troubleshooting

- **Container starts, then restarts every few seconds** — check the Deploy Logs
  tab. Most often it's a missing env var or a DB connection issue.
- **Static files (JS/CSS) return 404** — wait ~60s after deploy; the SPA is
  built inside the image during the `spa` stage and copied into `/app/static`.
- **Want to skip the SPA build?** The Dockerfile runs `npm run build` inside
  the image. To pre-build and commit `frontend/dist`, you can replace the
  `spa` stage with `COPY frontend/dist /app/static` (the source `frontend/`
  COPY would no longer be needed).
