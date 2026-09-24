# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# Railway's build context for this file is the repo root, even when the
# service has Root Directory = ./backend. (Docker builds from the repo
# root when picking up a Dockerfile at the root.) All COPY paths below
# are repo-root-relative.
#
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly
# with image_build_context: "./", so this file is irrelevant there.

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

# Stage the backend tree at /app/_backend_src so the editable install
# finds pyproject.toml and the package layout. Build context is the repo
# root, so each path is repo-root-relative.
COPY backend/pyproject.toml /app/_backend_src/pyproject.toml
COPY backend/app /app/_backend_src/app
COPY backend/alembic /app/_backend_src/alembic
COPY backend/alembic.ini /app/_backend_src/alembic.ini
COPY backend/scripts /app/_backend_src/scripts

RUN pip install --upgrade pip && pip install -e "/app/_backend_src[api]"

# Mirror the Python sources to /app/app so the entrypoint command
# (`python -m uvicorn app.main:app`) resolves at the conventional location.
RUN cp -r /app/_backend_src/app /app/app

COPY --from=spa /spa/dist /app/static

# Storage directories for the local-disk fallback.
RUN mkdir -p /app/storage/files /app/storage/avatars /app/storage/backups

# Run as a non-root user.
RUN useradd --create-home --uid 10001 --shell /bin/bash app \
    && chown -R app:app /app /app/_backend_src
USER app

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]

# Honour $PORT. Run migrations on every boot.
CMD ["bash", "-lc", "export PYTHONPATH=/app/_backend_src && alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
