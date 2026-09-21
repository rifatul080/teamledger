# TeamLedger — Plan

Five phases. Each step ends with a commit. Exit gates are run + read.

## Phase 1 — Architecture & skeleton
- [ ] 1.1 PLAN.md (this file) + README outline + .gitignore + .env.example
- [ ] 1.2 docs/requirements.md (IDs, acceptance criteria)
- [ ] 1.3 docs/architecture.md (system diagram, Mermaid ER, permission matrix, sequence diagrams, scoring design)
- [ ] 1.4 docs/adr/ (FastAPI, SQLAlchemy 2 + Alembic, Argon2, WebSockets, APScheduler, Vite+React+TanStack, scoring = pure Decimal module, file storage interface)
- [ ] 1.5 docs/test-plan.md + traceability skeleton
- [ ] 1.6 docs/ASSUMPTIONS.md (no Docker / no Postgres / no gh on this machine)
- [ ] 1.7 docker-compose.yml + Dockerfile (api, web, db, maildev)
- [ ] 1.8 Backend skeleton: FastAPI app, settings via pydantic-settings, SQLAlchemy 2 models, Alembic init, ruff + mypy strict
- [ ] 1.9 Frontend skeleton: Vite + React + TS strict, Tailwind, ESLint, Vitest, Playwright config
- [ ] 1.10 CI workflow (.github/workflows/ci.yml)
- [ ] 1.11 Exit gate: ruff + mypy + tsc pass, matrix has no empty cells

## Phase 2 — Implementation (vertical slices)
- [ ] 2.1 Accounts (signup/login/logout/reset/profile + Argon2 + httpOnly cookies + CSRF + rate limit)
- [ ] 2.2 Teams & membership (create, invite by email, accept, remove, transfer leader, archive)
- [ ] 2.3 Projects & tasks (project, paper, goal, milestone, task; status flow; member-proposed tasks)
- [ ] 2.4 Schedules & calendar (weekly availability, overload warning, calendar + timeline views)
- [ ] 2.5 Notifications (in-app + optional email; idempotent scheduler; 3d/1d/overdue)
- [ ] 2.6 File library (versioning, SHA-256, content-type sniffing, path-safe, archive sanity, ACL)
- [ ] 2.7 Chat (WebSocket per team, pagination, mentions, edit/delete, unread, reconnect safety, escape)
- [ ] 2.8 Scoring & author order (pure module, CRediT categories, multi-stage adjustments, snapshot, dashboard)
- [ ] 2.9 Exports (PDF + CSV + CRediT text statement)
- [ ] 2.10 Seed data (two teams, two papers, 5+5 participants, 12-week plan)

## Phase 3 — Testing
- [ ] 3.1 Service unit tests (incl. scoring: 40+ table cases + Hypothesis)
- [ ] 3.2 API tests with auth matrix auto-generated from docs/architecture.md
- [ ] 3.3 WebSocket tests (auth, ordering, reconnect, isolation)
- [ ] 3.4 File tests (empty, size boundary, double extensions, traversal, archive escape, ACL)
- [ ] 3.5 Concurrency tests (uploads, rating vs reassign, leadership transfer race)
- [ ] 3.6 Time tests (clock injection, month/DST, multi-tz, overdue, late steps)
- [ ] 3.7 Schemathesis against /api/v1/openapi.json
- [ ] 3.8 Playwright main flows + chat between 2 contexts
- [ ] 3.9 Scenario: twelve week paper (timer, late, rejected, removed, adjustment, finalize)
- [ ] 3.10 Load check (≈50 users chat for 60s, p95)
- [ ] 3.11 Static checks (ruff, mypy strict, tsc, ESLint, bandit, pip-audit, npm audit)
- [ ] 3.12 Coverage gates (90% backend services + scoring, 80% rest)
- [ ] 3.13 Exit gate: one command runs everything from clean checkout

## Phase 4 — Bug fixing
- [ ] 4.1 Run full suite + static checks vs fresh DB
- [ ] 4.2 Fix root cause + add regression test per failure
- [ ] 4.3 Adversarial self-review per category, log to docs/testing.md, fix findings
- [ ] 4.4 Repeat until 3 consecutive clean green runs

## Phase 5 — Documentation
- [ ] 5.1 README.md (run every command it lists)
- [ ] 5.2 docs/user-guide.md (worked example)
- [ ] 5.3 docs/scoring-methodology.md
- [ ] 5.4 docs/api.md (curl examples)
- [ ] 5.5 docs/architecture.md / docs/adr/ updated
- [ ] 5.6 docs/testing.md (filled traceability, coverage, load, review log)
- [ ] 5.7 docs/security.md
- [ ] 5.8 docs/deployment.md
- [ ] 5.9 docs/known-limitations.md, docs/ASSUMPTIONS.md, CHANGELOG.md
- [ ] 5.10 Exit gate: README walkthrough on clean machine works

## Publish
- [ ] GitHub repo teamledger (private). Try gh, fall back to git HTTPS with cached credential; otherwise document the exact publish commands. Tag v1.0.0.
