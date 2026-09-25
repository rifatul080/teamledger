"""Unit tests for the database URL normaliser in app.core.config."""
from __future__ import annotations

from app.core.config import Settings, _normalize_database_url


def test_normalise_bare_postgresql():
    assert _normalize_database_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_normalise_postgres_alias():
    assert _normalize_database_url("postgres://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_keeps_explicit_psycopg():
    assert _normalize_database_url("postgresql+psycopg://u:p@h/d") == "postgresql+psycopg://u:p@h/d"


def test_keeps_explicit_psycopg2():
    assert _normalize_database_url("postgresql+psycopg2://u:p@h/d") == "postgresql+psycopg2://u:p@h/d"


def test_keeps_sqlite():
    assert _normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_settings_applies_normalisation(monkeypatch):
    """Settings() should hand back a normalised URL when DATABASE_URL is bare."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    s = Settings()
    assert s.database_url == "postgresql+psycopg://u:p@h/d"


def test_settings_keeps_explicit_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@h/d")
    s = Settings()
    assert s.database_url == "postgresql+psycopg2://u:p@h/d"


def test_cookie_samesite_default_lax(monkeypatch):
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    assert Settings().cookie_samesite == "lax"


def test_cookie_samesite_env_overrides(monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    assert Settings().cookie_samesite == "none"
