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
        build-essential libpq-dev libmagic1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[api]"

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY --from=spa /spa/dist /app/static

RUN mkdir -p /app/storage/files /app/storage/avatars /app/storage/backups

EXPOSE 8000

CMD ["bash", "-lc", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
