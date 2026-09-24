# Root-level Dockerfile for Railway / Fly.io / Koyeb / any platform that
# auto-detects a Dockerfile at the repo root.
#
# This file is the Railway-friendly path. Railway's service has
# Root Directory = ./backend (per the user's setup), so the build context
# is ./backend. We probe for that and adapt — if Railway is using this
# Dockerfile at the repo root with a different context, the probe below
# still finds the backend tree by looking for `pyproject.toml`.
#
# For Cloudflare Containers, wrangler uses backend/Dockerfile directly
# with image_build_context: "./", so this file is irrelevant there.

# ---- Stage 1: build the SPA ----
FROM node:20-alpine AS spa
WORKDIR /spa

# The frontend lives at frontend/ when build context = repo root, or at
# ../frontend when context = ./backend. We copy from both possible
# locations and pick whichever succeeded.
COPY [ "./frontend/", "./frontend_a/" ]
COPY [ "../frontend/", "./frontend_b/" ]
RUN if [ -d ./frontend_a ]; then \
        echo "Using frontend from ./frontend (repo-root context)"; \
        rm -rf ./frontend_b 2>/dev/null || true; \
        cp -r ./frontend_a/* ./ && rm -rf ./frontend_a; \
    elif [ -d ./frontend_b ]; then \
        echo "Using frontend from ../frontend (./backend context)"; \
        rm -rf ./frontend_a 2>/dev/null || true; \
        cp -r ./frontend_b/* ./ && rm -rf ./frontend_b; \
    else \
        echo "ERROR: frontend/ not found in build context"; \
        exit 1; \
    fi

# Install deps and build. We always work from /spa (this stage's WORKDIR).
COPY package.json package-lock.json* ./
# npm ci fails without lockfile; use npm install when absent.
RUN npm install --no-audit --no-fund
COPY . ./
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

# Copy the backend source. The Dockerfile copies the build context (.) into
# /app/_backend_src. Two cases:
#   1. Build context = repo root: ./pyproject.toml is in the root, not
#      at ./backend/pyproject.toml — but `COPY .` gives us the whole repo,
#      so we then drill into ./backend/ to find the backend tree.
#   2. Build context = ./backend: `COPY .` gives us the backend tree
#      directly.
COPY . /app/_backend_src/

# Normalize: we want /app/_backend_src to BE the backend tree (with
# pyproject.toml, app/, alembic/, etc. at its root), regardless of which
# case we started with.
RUN if [ -f /app/_backend_src/pyproject.toml ]; then \
        echo "Build context = ./backend — /app/_backend_src is the backend tree"; \
    elif [ -f /app/_backend_src/backend/pyproject.toml ]; then \
        echo "Build context = repo root — drilling into ./backend"; \
        rm -rf /app/_backend_src_inner; \
        mv /app/_backend_src /app/_backend_src_inner; \
        mv /app/_backend_src_inner/backend /app/_backend_src; \
        rm -rf /app/_backend_src_inner; \
    else \
        echo "ERROR: backend source tree not found in build context"; \
        ls -la /app/_backend_src; \
        exit 1; \
    fi

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
