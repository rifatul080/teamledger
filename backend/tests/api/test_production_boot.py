"""Boot the app under APP_ENV=production against SQLite.

The Dockerfile runs ``APP_ENV=production alembic upgrade head && uvicorn ...``,
so the production config path is reached on every container start. This
test mirrors that and ensures no Settings field has grown mandatory in a
way that would crash a fresh deploy.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture
def prod_env(monkeypatch, tmp_path) -> Iterator[None]:
    db = tmp_path / "prod.sqlite"
    storage = tmp_path / "files"
    avatars = tmp_path / "avatars"
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(storage))
    monkeypatch.setenv("AVATAR_LOCAL_ROOT", str(avatars))
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "https://teamledger.example.com"
    )
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://teamledger.example.com")
    monkeypatch.setenv("MAIL_BACKEND", "console")
    storage.mkdir(parents=True, exist_ok=True)
    avatars.mkdir(parents=True, exist_ok=True)
    # Reset the settings cache + engine singleton so the monkeypatched env
    # actually wins.
    from app.core.config import get_settings
    from app.db.session import reset_engine_for_tests

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_engine_for_tests()
    yield


def test_app_starts_in_production_mode(prod_env) -> None:
    """The full create_app path runs without raising on production config.

    Catches accidental growth of required Settings fields.
    """
    from app.core.config import get_settings
    from app.main import create_app

    s = get_settings()
    assert s.app_env == "production"
    assert s.database_url.startswith("sqlite:///")
    # The CORS parser splits on commas and trims whitespace.
    assert s.cors_origins == ["https://teamledger.example.com"]
    assert s.public_base_url == "https://teamledger.example.com"

    # App boots without missing-mandatory errors.
    a = create_app()
    assert a.title.startswith("TeamLedger")


def test_alembic_runs_against_fresh_db(prod_env) -> None:
    """The Dockerfile's CMD runs `alembic upgrade head` before uvicorn —
    replicate that flow here against a fresh SQLite DB."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config as AlembicConfig
    from app.core.config import get_settings
    from sqlalchemy import create_engine, inspect

    s = get_settings()
    cfg = AlembicConfig(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", s.database_url)
    command.upgrade(cfg, "head")

    eng = create_engine(s.database_url, connect_args={"check_same_thread": False})
    insp = inspect(eng)
    tables = insp.get_table_names()
    # A representative subset — if any of these are missing, alembic
    # didn't run cleanly and the container would crash on first request.
    for required in ("users", "teams", "memberships", "invitations"):
        assert required in tables, f"missing table after migrate: {required}"
