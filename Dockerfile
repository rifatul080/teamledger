# Root-level Dockerfile for Railway / Fly.io / Koyeb / Render / any
# platform that auto-detects a Dockerfile at the repo root.
#
# Build context: REPOSITORY ROOT.
#
# CACHE BUSTER: bump the value below whenever COPY paths change to
# force Render's BuildKit cache to invalidate. Render aggressively
# reuses cached layers across deploys, and a stale cache from a
# previous (failed) build can persist with the wrong context snapshot
# and fail forever with errors like "/backend/app/__init__.py": not
# found. Bumping this forces a clean rebuild.
#
# IMPORTANT for Railway: this Dockerfile expects the build context to be
# the repo root (so it can `COPY backend/...` and `COPY frontend/...`).
# If your Railway service's "Root Directory" is set to ./backend, the
# build context becomes backend/ instead and this file will fail with
# errors like "/backend/app/__init__.py": not found. Set the service's
# Root Directory to "" (empty) or "." on Railway so the full repo is
# sent as the build context.
#
# backend/Dockerfile is the alternative for platforms that insist on a
# ./backend context (Cloudflare Containers with image_build_context: "./").
#
# Final layout:
#   /app/pyproject.toml       <- editable install target
#   /app/alembic.ini          <- alembic cwd-relative config
#   /app/alembic/             <- alembic migrations
#   /app/app/                 <- Python package (importable as `app`)
#   /app/app/main.py          <- uvicorn entrypoint (app.main:app)
#   /app/scripts/             <- helper scripts
#   /app/static/              <- built SPA (served by FastAPI)
#   /app/storage/             <- local-disk fallback

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

# Cache buster — see comment at top of file. Bump on COPY-path changes.
ARG CACHE_BUST=3
RUN echo "cache-bust=$CACHE_BUST" > /tmp/cache_bust

# All paths below are repo-root-relative.
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
# Copy the entire backend/app tree as one unit so we don't silently drop
# files (e.g. main.py) that aren't in any sub-package directory. This
# includes the just-restored __init__.py marker files for the `app`
# and `app.api` packages.
COPY backend/app /app/app
COPY backend/scripts /app/scripts

# Sanity-check: fail the build loud if the storage Python package is
# missing (e.g. if app/storage/ wasn't tracked in git).
RUN test -f /app/app/storage/__init__.py \
 && test -f /app/app/storage/base.py \
 && test -f /app/app/storage/local.py \
 && echo "storage package present: $(ls /app/app/storage)"

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
