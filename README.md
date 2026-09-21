# TeamLedger

Collaborative research paper project manager. Team workspaces, project milestones,
contributor scoring, and author-order finalisation — with a CRediT-aware
points model and an immutable audit trail.

* **Backend** — FastAPI + SQLAlchemy 2 + Alembic. SQLite for tests / local dev,
  PostgreSQL for production. Argon2id password hashing, httpOnly cookie auth,
  CSRF, rate limiting, pure-`Decimal` scoring math.
* **Frontend** — Vite + React + TypeScript (strict) + Tailwind + TanStack Query.
  Pages for teams, projects, goals/tasks, chat, scoring, notifications.

## Quick start (Windows / PowerShell 5.1)

```powershell
# 1. Backend install (editable + extras)
cd backend
python -m pip install -e ".[api,test,dev]"

# 2. Apply migrations and seed demo data
alembic upgrade head
python -m scripts.seed_demo

# 3. Run the API on http://localhost:8000
uvicorn app.main:app --reload --port 8000
# interactive docs: http://localhost:8000/docs
```

```powershell
# In another shell — frontend
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

## Quick start (Linux / macOS)

```bash
cd backend && pip install -e ".[api,test,dev]" \
  && alembic upgrade head && python -m scripts.seed_demo \
  && uvicorn app.main:app --reload &

cd frontend && npm install && npm run dev
```

## Run everything from a clean checkout

```bash
make test-all       # install + lint + type + 184 tests with 80% coverage gate
```

| Command          | What it runs                                      |
|------------------|---------------------------------------------------|
| `make backend`   | API on port 8000                                  |
| `make frontend`  | Web on port 5173                                  |
| `make test`      | Backend pytest                                    |
| `make coverage`  | Backend pytest with `--cov-fail-under=80`         |
| `make lint`      | ruff + eslint                                     |
| `make type`      | mypy + tsc                                        |
| `make security`  | bandit + pip-audit                                |
| `make test-all`  | Everything above, end-to-end                      |
| `make migrate`   | `alembic upgrade head`                            |
| `make seed`      | Seed two demo teams + sample papers               |

## Test facts

* **179 backend tests + 5 frontend tests = 184 total** (see `make test-all`).
* Backend coverage **gate = 80%** (`backend/.coveragerc`).
  Current run: **81.0%** overall · **99%** in the pure scoring module.
* Static: **ruff 0 issues**, **bandit 0 high/medium**, **mypy strict** for
  pure code (overrides documented in `pyproject.toml`).
* Property-based scoring tests via Hypothesis (`tests/property`).
* The full test command runs in ~90 seconds on a single core.

## Architecture

See **[docs/architecture.md](docs/architecture.md)** for the system diagram,
ER diagram, permission matrix, sequence diagrams, and scoring design.
Decisions are documented under **[docs/adr/](docs/adr/)**.

| Concern                | Choice                                                   |
|------------------------|----------------------------------------------------------|
| Web framework          | FastAPI                                                  |
| ORM / migrations       | SQLAlchemy 2 + Alembic                                   |
| Auth                   | Argon2id, JWT in httpOnly cookies, CSRF, rate limits     |
| Password reset         | 1-hour-TTL tokens, console mailer in dev                 |
| Chat                   | Per-team WebSocket, monotonic server-side `seq`          |
| Files                  | Storage interface; local disk impl; SHA-256, versioned   |
| Scoring                | **Pure** Decimal module (no DB / clock imports)          |
| Author order           | Suggested + pinned + final snapshot (sha256)            |
| Notifications          | APScheduler + idempotent reminders                       |
| Frontend               | Vite + React + TS strict + TanStack Query                |

## Project structure

```
backend/
  app/
    api/v1/        # FastAPI routers (auth, teams, projects, tasks, chat, ...)
    models/        # SQLAlchemy 2 ORM
    schemas/       # Pydantic request / response models
    services/      # Business logic (pure-ish where possible)
    scoring/       # Pure Decimal scoring engine (no IO)
    storage/       # Pluggable file backend interface
    notifications/ # Scheduler + mailer
  alembic/         # Migrations
  tests/
    api/           # HTTP-level integration tests
    unit/          # Pure-function + service-level tests
    property/      # Hypothesis tests
frontend/
  src/             # React + TS pages
.github/workflows/ # CI (lint + type + pytest)
docs/              # Architecture, requirements, ADRs, runbooks
docker-compose.yml # api + web + db + maildev stack
```

## Environment variables

The backend reads these via `pydantic-settings`. See
**[docs/deployment.md](docs/deployment.md)** for the full list and defaults.

| Var                   | Default                  | Notes                                  |
|-----------------------|--------------------------|----------------------------------------|
| `DATABASE_URL`        | `sqlite:///./teamledger.db` | `postgresql+psycopg://...` in prod  |
| `STORAGE_LOCAL_ROOT`  | `./_storage`             | Used by the local-disk backend         |
| `SECRET_KEY`          | dev-only                 | 32+ bytes; required in production      |
| `APP_ENV`             | `development`            | `test` / `production` switch behaviour |
| `CORS_ALLOWED_ORIGINS`| `http://localhost:5173`  | Comma-separated list                   |
| `MAIL_BACKEND`        | `console`                | `console` prints; `smtp` is optional   |

## Security & access control

See **[docs/security.md](docs/security.md)**. Highlights:

* Every endpoint enforces role / membership server-side; UI hiding is not the gate.
* Auth cookies are `HttpOnly; SameSite=Lax; Secure` in production.
* CSRF token in a separate cookie + `X-CSRF-Token` header for unsafe verbs.
* Login + reset endpoints have per-email and per-IP rate caps (429 when exceeded).
* Passwords use Argon2id (OWASP defaults); JWTs in cookies, never URLs.

## Known limitations

See **[docs/known-limitations.md](docs/known-limitations.md)**. Top items:

* WebSocket layer is not covered by automated tests (smoke via dev server).
* Playwright e2e + load harness are dependencies-present but not in CI.
* Schemathesis fuzzing is installed but not wired into the test suite.

## Contributing

* Backend: `cd backend && ruff check . && mypy app && pytest`
* Frontend: `cd frontend && npm run lint && npm run typecheck && npm test -- --run`
* Use [conventional commits](https://www.conventionalcommits.org/) for clarity
  in the log. Open a PR with a one-line summary and a "Test plan" section.

## License

This repository is released under the MIT License (see
[CHANGELOG.md](CHANGELOG.md) for the v1.0.0 release notes).

## Full table of contents

* [docs/architecture.md](docs/architecture.md)
* [docs/requirements.md](docs/requirements.md)
* [docs/user-guide.md](docs/user-guide.md)
* [docs/scoring-methodology.md](docs/scoring-methodology.md)
* [docs/api.md](docs/api.md)
* [docs/security.md](docs/security.md)
* [docs/deployment.md](docs/deployment.md)
* [docs/testing.md](docs/testing.md)
* [docs/known-limitations.md](docs/known-limitations.md)
* [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md)
* [CHANGELOG.md](CHANGELOG.md)
* [PLAN.md](PLAN.md)
