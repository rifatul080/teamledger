# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# Build context must be the repo root (clear the service's "Root Directory"
# setting in Railway, otherwise this won't find frontend/, backend/app, etc.).
#
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly with
# image_build_context: "./", so this file is irrelevant there.

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

# Install backend deps. We COPY the whole backend/ tree into a staging
# directory and pip-install it editable so that the `teamledger-backend`
# metadata is set up correctly (alembic needs the metadata to find its
# config). The editable install adds a `.pth` file that points at
# /app/_backend_src — that's the canonical home for the Python `app`
# package.
COPY backend/ /app/_backend_src/
RUN pip install --upgrade pip && pip install -e "/app/_backend_src[api]"

# Mirror the backend Python sources to /app/app so the entrypoint command
# (`python -m uvicorn app.main:app`) resolves at the conventional location,
# and so debugging with `docker exec` / `ls /app/app` matches the Cloudflare
# Containers image layout. The editable install still points at
# /app/_backend_src, so the `app` import continues to work even if you
# delete /app/app later.
RUN cp -r /app/_backend_src/app /app/app \
    && cp -r /app/_backend_src/alembic /app/alembic \
    && cp /app/_backend_src/alembic.ini /app/alembic.ini \
    && cp -r /app/_backend_src/scripts /app/scripts

COPY --from=spa /spa/dist /app/static

# Storage directories for the local-disk fallback (avatars, files, backups).
# On managed Postgres (Neon, etc.) the SQLite DB at /app/storage/ is unused,
# but we keep the directory so a SQLite-only deploy still works.
RUN mkdir -p /app/storage/files /app/storage/avatars /app/storage/backups

# Run as a non-root user. Most PaaS platforms warn (or refuse) on root
# containers.
RUN useradd --create-home --uid 10001 --shell /bin/bash app \
    && chown -R app:app /app /app/_backend_src
USER app

# Railway (and most PaaS) sets PORT dynamically. The CMD script reads $PORT
# and falls back to 8000 when unset. Cloudflare sets PORT=8080 explicitly
# in src/container.ts.
ENV PORT=8080
EXPOSE 8080

# tini reaps zombies and forwards signals so SIGTERM from the orchestrator
# actually shuts uvicorn down cleanly.
ENTRYPOINT ["/usr/bin/tini", "--"]

# Honour $PORT (Railway injects one). Run migrations on every boot — this
# is idempotent and ensures schema is in sync at deploy time. We add the
# editable-install source to PYTHONPATH so the `app` import resolves
# without depending on /app/app (which is just a debugging mirror).
CMD ["bash", "-lc", "export PYTHONPATH=/app/_backend_src && alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
