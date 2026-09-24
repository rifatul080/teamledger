# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# Railway's service has Root Directory = ./backend, so Docker's build
# context is ./backend. All COPY paths are relative to that context.
# The frontend lives at ../frontend (one level up from the build context).
#
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly
# with image_build_context: "./", so this file is irrelevant there.

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS spa
WORKDIR /spa
COPY ../frontend/package.json ../frontend/package-lock.json* ./
# npm ci fails without lockfile; use npm install when absent (dev installs).
RUN npm install --no-audit --no-fund
COPY ../frontend ./
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
# finds pyproject.toml and the package layout. Build context is ./backend
# (Railway's Root Directory), so each path is a direct child of the
# context root — except pyproject.toml which lives at the context root
# itself.
COPY ./pyproject.toml /app/_backend_src/pyproject.toml
COPY ./app /app/_backend_src/app
COPY ./alembic /app/_backend_src/alembic
COPY ./alembic.ini /app/_backend_src/alembic.ini
COPY ./scripts /app/_backend_src/scripts

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
