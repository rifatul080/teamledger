# backend/Dockerfile — used by Cloudflare Containers with
# image_build_context: "./" in wrangler.jsonc (build context = repo root).
#
# For Railway / Render / Fly / etc. the root-level Dockerfile handles the
# build instead, and adapts to its build context.

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

COPY ./pyproject.toml /app/_backend_src_pyproject.toml
COPY ./alembic /app/_backend_src_alembic
COPY ./app /app/_backend_src_app

# Reassemble the backend tree at /app/_backend_src so the editable install
# sees pyproject.toml and the package layout.
RUN mkdir -p /app/_backend_src && \
    mv /app/_backend_src_pyproject.toml /app/_backend_src/pyproject.toml && \
    cp -r /app/_backend_src_alembic /app/_backend_src/alembic && \
    cp -r /app/_backend_src_app /app/_backend_src/app

RUN pip install --upgrade pip && pip install -e "/app/_backend_src[api]"

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

CMD ["bash", "-lc", "export PYTHONPATH=/app/_backend_src && alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
