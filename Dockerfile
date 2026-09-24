# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# Build context = repo root. All COPY paths are repo-root-relative.
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly
# with image_build_context: "./", so this file is irrelevant there.
#
# Layout (kept simple on purpose):
#   /app/pyproject.toml       <- editable install target
#   /app/alembic.ini          <- alembic cwd-relative config
#   /app/alembic/             <- alembic migrations
#   /app/app/                 <- Python package (importable as `app`)
#   /app/app/main.py          <- uvicorn entrypoint (app.main:app)
#   /app/scripts/             <- helper scripts
#   /app/static/              <- built SPA (served by FastAPI)
#   /app/storage/             <- local-disk fallback (avatars, files, backups)

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS spa
WORKDIR /spa
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend ./
RUN npm run build

# ---- Stage 2: backend + serve SPA ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev libmagic1 curl ca-certificates tini \
    && rm -rf /var/lib/apt/lists/*

# Copy the backend directly to /app. `python -m uvicorn app.main:app` run
# from /app resolves `app` to /app/app. `alembic upgrade head` run from
# /app finds /app/alembic.ini (script_location = alembic -> /app/alembic).
# `pip install -e /app[api]` installs the `app` package importable from
# anywhere via the editable-install .pth file.
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
# Copy the Python package and every sub-package explicitly. Using a single
# `COPY backend/app /app/app` works in local builds, but the storage/
# sub-package has been getting dropped on some BuildKit deployments (it
# appears to silently conflict with the .dockerignore pattern
# `backend/storage/**` — different path, same prefix). Listing every
# sub-dir avoids the ambiguity.
COPY backend/app/__init__.py /app/app/__init__.py
COPY backend/app/api /app/app/api
COPY backend/app/core /app/app/core
COPY backend/app/db /app/app/db
COPY backend/app/models /app/app/models
COPY backend/app/notifications /app/app/notifications
COPY backend/app/realtime /app/app/realtime
COPY backend/app/schemas /app/app/schemas
COPY backend/app/scoring /app/app/scoring
COPY backend/app/services /app/app/services
COPY backend/app/storage /app/app/storage
COPY backend/scripts /app/scripts

RUN pip install --upgrade pip && pip install -e "/app[api]"

COPY --from=spa /spa/dist /app/static

RUN mkdir -p /app/storage/files /app/storage/avatars /app/storage/backups

RUN useradd --create-home --uid 10001 --shell /bin/bash app \
    && chown -R app:app /app
USER app

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]

# Honour $PORT. Run migrations on every boot.
CMD ["bash", "-lc", "alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
