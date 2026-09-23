# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# This is a near-identical copy of backend/Dockerfile but with
# repo-root-relative COPY paths, since Railway builds with the repo root as
# the build context.
#
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly
# (with image_build_context: "./"), so this file is irrelevant there.

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS spa
WORKDIR /spa
COPY frontend/package.json frontend/package-lock.json* ./
# npm ci fails without lockfile; use npm install when absent (dev installs).
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

COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[api]"

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY --from=spa /spa/dist /app/static

# Storage directories for the local-disk fallback (avatars, files, backups).
# On managed Postgres (Neon, etc.) the SQLite DB at /app/storage/ is unused,
# but we keep the directory so a SQLite-only deploy still works.
RUN mkdir -p /app/storage/files /app/storage/avatars /app/storage/backups

# Run as a non-root user. Most PaaS platforms warn (or refuse) on root
# containers.
RUN useradd --create-home --uid 10001 --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Railway (and most PaaS) sets PORT dynamically. The CMD script reads $PORT
# and falls back to 8000 when unset. Cloudflare sets PORT=8080 explicitly
# in src/container.ts.
ENV PORT=8080
EXPOSE 8080

# tini reaps zombies and forwards signals so SIGTERM from the orchestrator
# actually shuts uvicorn down cleanly.
ENTRYPOINT ["/usr/bin/tini", "--"]

# Honour $PORT (Railway injects one). Run migrations on every boot — this is
# idempotent and ensures schema is in sync at deploy time.
CMD ["bash", "-lc", "alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
