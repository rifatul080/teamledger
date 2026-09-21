# ADR-0002 — SQLAlchemy 2 + Alembic + Postgres (SQLite fallback)

- **Status:** accepted
- **Context:** Spec says SQLAlchemy 2, Alembic, Postgres. Local dev environment has no Docker/Postgres.
- **Decision:** SQLAlchemy 2 with declarative `Mapped[...]` types, Alembic migrations targeting Postgres. Add an SQLite compatibility profile gated by `DATABASE_URL` for local quick-start only.
- **Consequences:**
  - Identical SQLAlchemy core works against both engines for the unit tests we run locally.
  - Tests that exercise Postgres-specific features (e.g. `tsvector`, `FOR UPDATE SKIP LOCKED`) are run in CI only; local runs skip them with a clear marker.
  - Migration scripts authored against Postgres and reviewed in CI; SQLite uses raw-SQL Alembic operations only.
- **Alternatives considered:**
  - Pure Postgres only — would block local iteration; rejected.
  - Pure SQLite — would miss Postgres-specific concurrency semantics in the scoring snapshot/notification tests; rejected.
