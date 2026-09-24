# backend/Dockerfile — used by Cloudflare Containers with
# image_build_context: "./" in wrangler.jsonc (build context = repo root).
# All COPY paths here are relative to the build context root (./), so
# `frontend/`, `backend/`, etc. are repo-root-relative paths.
#
# This Dockerfile is identical in structure to the root-level Dockerfile,
# the only difference being the COPY paths start with `backend/` (because
# the build context is the repo root).
#
# Layout:
#   /app/pyproject.toml
#   /app/alembic.ini
#   /app/alembic/
#   /app/app/                 <- importable as `app`
#   /app/scripts/
#   /app/static/              <- SPA
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

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/app /app/app
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

CMD ["bash", "-lc", "alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
