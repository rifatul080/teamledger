# backend/Dockerfile — used by Cloudflare Containers with
# image_build_context: "./" in wrangler.jsonc (build context = repo root).
# All COPY paths here are relative to the build context root (./), so
# `frontend/`, `backend/`, etc. are repo-root-relative paths.
#
# For Railway / Render / Fly / etc. the root-level Dockerfile handles the
# build instead, and adapts to its build context.
#
# Note on Docker COPY semantics: paths in COPY are resolved relative to
# the build context root, NOT to the Dockerfile's directory. So even
# though this Dockerfile lives in backend/, `COPY backend ./` works
# (because the build context is the repo root and `./backend` exists).

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
# finds pyproject.toml and the package layout. COPY paths are
# repo-root-relative (build context is ./).
COPY backend /app/_backend_src/

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

CMD ["bash", "-lc", "export PYTHONPATH=/app/_backend_src && alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
