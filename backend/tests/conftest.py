"""Shared test fixtures and helpers."""
from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock, FakeClock
from app.core.security import hash_password
from app.core.tokens import encode_jwt
from app.db.base import Base
from app.db.session import get_sessionmaker, reset_engine_for_tests
from app.main import create_app


@pytest.fixture(scope="function")
def tmp_storage(tmp_path: Path) -> Path:
    """Per-test storage root."""
    root = tmp_path / "files"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="function")
def db_engine(tmp_path: Path, tmp_storage: Path, monkeypatch):
    """Per-test fresh SQLite database with migrations applied."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_storage))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32-bytes-minimum-please")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MAIL_BACKEND", "console")
    # Clear cached settings singleton so monkeypatched env vars are picked up.
    from app.core.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()
    # Apply schema
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    yield engine
    reset_engine_for_tests()
    get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(scope="function")
def db(db_engine) -> Iterator[Session]:
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="function")
def app(db_engine):
    """FastAPI app wired to the per-test database."""
    from app.api.deps import get_db
    from app.api.rate_limit import limiter
    from app.core.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    limiter.reset()  # clear cross-test rate-limit state
    application = create_app()
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    application.dependency_overrides[get_db] = _get_db
    yield application
    application.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def clock() -> FakeClock:
    """Injectable clock for time-dependent tests."""
    return FakeClock(start=datetime(2025, 1, 1, tzinfo=timezone.utc))


@pytest.fixture
def make_user(db: Session):
    def _factory(email: str = None, display_name: str = "Test User", password: str = "Password1Demo", tz: str = "UTC") -> Any:
        from app.models.user import User

        u = User(
            id=str(uuid.uuid4()).replace("-", "")[:26],
            email=(email or f"u-{uuid.uuid4().hex[:8]}@example.org"),
            display_name=display_name,
            timezone=tz,
            password_hash=hash_password(password),
            is_active=True,
            created_at=datetime.now(tz=timezone.utc),
        )
        db.add(u)
        db.flush()
        return u

    return _factory


@pytest.fixture
def auth_headers():
    def _factory(user_id: str, *, csrf: str = "test-csrf") -> dict[str, str]:
        token = encode_jwt({"sub": user_id, "email": "x@example.org"}, ttl_seconds=600)
        return {
            "Authorization": f"Bearer {token}",
            "X-CSRF-Token": csrf,
        }

    return _factory


@pytest.fixture
def seed_team(db, make_user):
    """Returns a leader + member + team."""
    from app.models.membership import Membership
    from app.models.team import Team

    leader = make_user(email="leader@example.org", display_name="Leader")
    member = make_user(email="member@example.org", display_name="Member")
    team = Team(
        id=str(uuid.uuid4()).hex[:26],
        name="Test Team",
        description="",
        archived=False,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(team)
    db.flush()
    db.add(
        Membership(
            id=str(uuid.uuid4()).hex[:26],
            user_id=leader.id,
            team_id=team.id,
            role="leader",
            joined_at=team.created_at,
            created_at=team.created_at,
        )
    )
    db.add(
        Membership(
            id=str(uuid.uuid4()).hex[:26],
            user_id=member.id,
            team_id=team.id,
            role="member",
            joined_at=team.created_at,
            created_at=team.created_at,
        )
    )
    db.commit()
    return {"leader": leader, "member": member, "team": team}
