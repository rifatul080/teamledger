# Deployment

TeamLedger is a 12-factor app. The same image runs in `development`,
`staging`, and `production`; only environment variables differ.

## Components

| Component        | Image (recommended)                | Notes                              |
|------------------|------------------------------------|------------------------------------|
| API (FastAPI)    | `backend/Dockerfile` (uvicorn)     | Listens on `:8000`                 |
| Web (Vite/React) | `frontend/Dockerfile` (nginx)      | Static bundle, `/api` proxied      |
| Database         | Postgres 16                        | Or any SQLAlchemy-2-compatible DB  |
| Mail dev         | `maildev/maildev`                  | Dev only                           |

`docker-compose.yml` brings up the full stack for local integration.

## Environment variables

All variables are read by `app.core.config.Settings` (pydantic-settings).

### Required

| Var                | Example                                | Purpose                                |
|--------------------|----------------------------------------|----------------------------------------|
| `SECRET_KEY`       | `b3l...` (≥ 32 bytes, base64-equivalent) | Signs JWTs; rotates invalidate all tokens |
| `DATABASE_URL`     | `postgresql+psycopg://teamledger:...@db/teamledger` | DB connection |

### Recommended in production

| Var                       | Default                  | Notes                                         |
|---------------------------|--------------------------|-----------------------------------------------|
| `APP_ENV`                 | `development`            | Set `production` to harden cookies, etc.      |
| `CORS_ALLOWED_ORIGINS`    | `http://localhost:5173`  | Comma-separated allowlist                     |
| `TRUSTED_HOSTS`           | `*`                      | Comma-separated; sets `Host` validator        |
| `ACCESS_TOKEN_TTL_SECONDS`| 900                      | Short-lived access token                      |
| `REFRESH_TOKEN_TTL_DAYS`  | 30                       | Long-lived refresh token                      |
| `LOGIN_RATE_LIMIT_PER_MIN`| 10                       | Per email                                     |
| `RESET_RATE_LIMIT_PER_MIN`| 5                        | Per email                                     |
| `STORAGE_BACKEND`         | `local`                  | `local` (disk) or `s3` (planned)              |
| `STORAGE_LOCAL_ROOT`      | `./_storage`             | Required when `STORAGE_BACKEND=local`         |
| `DATABASE_URL`            | `sqlite:///./teamledger.db` | **Override** with Postgres in prod          |
| `MAIL_BACKEND`            | `console`                | `console` (dev), `smtp` (prod, optional)      |

### Optional — Postgres-only

| Var                       | Default                  | Notes                                         |
|---------------------------|--------------------------|-----------------------------------------------|
| `DATABASE_POOL_SIZE`      | 10                       | SQLAlchemy connection pool                    |
| `DATABASE_MAX_OVERFLOW`   | 5                        | Extra connections beyond the pool              |

## Database migrations

```bash
cd backend
alembic upgrade head
```

On startup, the application does **not** auto-run migrations. Run them as a
separate release step (Kubernetes Job, release pipeline).

## Docker

```bash
# Build
cd backend && docker build -t teamledger-api .
cd frontend && docker build -t teamledger-web ../frontend

# Run with compose
docker compose up -d
```

The compose file ships:

* `api` (FastAPI)
* `web` (nginx serving the Vite build, proxying `/api` to the API)
* `db` (Postgres 16)
* `maildev` (dev-only mail catcher on `:1080`)

## Reverse proxy / TLS

* Terminate TLS at the proxy (nginx, Caddy, Traefik, ALB).
* Forward `X-Forwarded-Proto` so the API emits `Secure` cookies.
* HSTS in `docs/security.md`.

## Health, liveness, readiness

| Path                | Use                                                  |
|---------------------|------------------------------------------------------|
| `/api/v1/health`    | Liveness — process alive                             |
| `/api/v1/health/db` | Readiness — DB reachable, schema migrations applied  |

Both are unauthenticated and safe to scrape.

## Backups

* `pg_dump --schema=public --no-owner teamledger > snapshot.sql` is
  sufficient for a small team. For larger instances use the managed
  Postgres backup feature.
* File storage is on disk in `STORAGE_LOCAL_ROOT`. Mirror with `rsync` to
  an object store bucket; tar + upload nightly.

## Observability

* Structured logs to stdout — the platform collects them.
* Set `LOG_LEVEL=info` in production; `debug` only in dev.
* The scoring module emits a `score.compute` log line per request with the
  formula version. Forwarding to your metrics pipeline is recommended.

## Capacity planning

The system is sized for **10–50 active researchers** per server:

* ~200 MB RAM at idle (SQLAlchemy pool + worker).
* ~100 KB per chat message (DB row + payload).
* Score computation is O(participants × tasks) and runs in well under
  100 ms on real data.

## Rollout checklist

1. `SECRET_KEY` rotated and stored in the secret manager.
2. `DATABASE_URL` points to a writeable Postgres instance.
3. `alembic upgrade head` completed on the new database.
4. `STORAGE_LOCAL_ROOT` mounted with persistence.
5. CORS allowlist set to the public web origin.
6. Health checks pass: `curl /api/v1/health/db` returns `200`.
7. Smoke run: login, create team, post a message, post a task.
8. Tag `vX.Y.Z` and push.

## Disaster recovery

* DB backup retention: 30 days.
* File backup retention: 90 days.
* `SECRET_KEY` rotation procedure:
  1. Deploy with both old + new keys (multi-key supported by
     `app/core/tokens.py`).
  2. After grace period, switch to the new key only.
  3. Old tokens are invalidated on next refresh.
