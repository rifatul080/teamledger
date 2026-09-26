"""Health endpoints: liveness + database readiness.

Render's own health check hits ``/healthz`` (registered in ``app/main.py``).
These two endpoints live inside the versioned API namespace and are what
external probes should scrape:

* ``GET /api/v1/health``    — liveness: the process is accepting requests.
* ``GET /api/v1/health/db`` — readiness: the database answers ``SELECT 1``.

Both are unauthenticated, read-only and cheap. ``/health/db`` deliberately
opens a database connection so that a periodic ping also keeps a Neon
compute from scaling to zero (Neon suspends an idle compute after 5
minutes on the Free plan).

Documented in ``docs/deployment.md`` § "Health, liveness, readiness".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...core.errors import AppError

router = APIRouter(prefix="/health", tags=["health"])

SERVICE_NAME = "teamledger-api"


@router.get("")
def health() -> dict[str, str]:
    """Liveness probe — no I/O, so it stays fast under any condition."""
    return {"status": "ok", "service": SERVICE_NAME}


def _migration_revision(db: Session) -> str | None:
    """Best-effort read of the Alembic revision applied to the database.

    Returns ``None`` (instead of raising) when ``alembic_version`` is
    missing — e.g. a database that has never been migrated. The probe's job
    is to report reachability, so migration state is reported as data
    rather than as a failure.
    """
    try:
        row = db.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception:
        return None
    return str(row[0]) if row else None


@router.get("/db")
def health_db(db: Session = Depends(get_db)) -> dict[str, str | None]:
    """Readiness probe — 503 when the database cannot be reached.

    Safe to expose publicly: it reports only a status flag and the applied
    migration revision, never connection details.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(
            status_code=503,
            code="db.unavailable",
            message="Database is not reachable.",
            details={"error": type(exc).__name__},
        ) from None
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "database": "ok",
        "migration": _migration_revision(db),
    }
