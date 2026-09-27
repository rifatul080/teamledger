"""Health / readiness probes (docs/deployment.md § Health, liveness, readiness).

These endpoints are the supported scrape targets for uptime monitors and
keep-alive pings, so the contract they expose is worth locking down.
"""
from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine


@pytest.mark.req_id("OPS-01")
def test_liveness_ok(client) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "teamledger-api"


@pytest.mark.req_id("OPS-01")
def test_liveness_needs_no_auth(client) -> None:
    # A probe must work without cookies or an Authorization header.
    assert client.get("/api/v1/health").status_code == 200


@pytest.mark.req_id("OPS-01")
def test_readiness_reports_database_and_migration(client) -> None:
    r = client.get("/api/v1/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    # The db_engine fixture runs `alembic upgrade head`, so a revision exists.
    assert body["migration"]


@pytest.mark.req_id("OPS-01")
def test_readiness_returns_503_when_database_unreachable(client, app) -> None:
    """A dead database must surface as 503 + the standard error envelope."""
    from app.api import deps

    class _BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

        def close(self) -> None:  # pragma: no cover - teardown only
            pass

    def _broken_db():
        yield _BrokenSession()

    app.dependency_overrides[deps.get_db] = _broken_db
    try:
        r = client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.pop(deps.get_db, None)

    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "db.unavailable"
    assert body["message"]


@pytest.mark.req_id("OPS-01")
def test_health_db_reports_driver_and_ephemeral_flag(client) -> None:
    """Operators need to see at a glance that the DB is disposable."""
    r = client.get("/api/v1/health/db")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["driver"] == "sqlite"  # the test harness runs on SQLite
    assert body["ephemeral"] is True


def _stub_engine(driver: str) -> Engine:
    """A minimal stand-in for an Engine: the guard only reads dialect.name."""
    from typing import cast

    from sqlalchemy.engine import Engine

    class _Dialect:
        name = driver

    class _StubEngine:
        dialect = _Dialect()

    return cast(Engine, _StubEngine())


@pytest.mark.parametrize("app_env", ["production", "development", "test"])
def test_ephemeral_db_warning_only_fires_for_production_sqlite(monkeypatch, app_env) -> None:
    """A production SQLite file is wiped on every deploy, so say so loudly."""
    from app.core.config import get_settings
    from app.main import ephemeral_db_warning

    monkeypatch.setenv("APP_ENV", app_env)
    get_settings.cache_clear()
    try:
        message = ephemeral_db_warning(_stub_engine("sqlite"))
        if app_env == "production":
            assert message is not None
            assert "ephemeral" in message
        else:
            assert message is None
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("driver", ["postgresql", "mysql"])
def test_ephemeral_db_warning_quiet_for_managed_databases(monkeypatch, driver) -> None:
    """A managed database is the intended setup, so stay quiet about it."""
    from app.core.config import get_settings
    from app.main import ephemeral_db_warning

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        assert ephemeral_db_warning(_stub_engine(driver)) is None
    finally:
        get_settings.cache_clear()


def test_warn_on_ephemeral_db_logs_the_warning(monkeypatch) -> None:
    """The boot-time hook must actually emit the message it computed."""
    from app import main as main_mod
    from app.core.config import get_settings

    errors: list[str] = []

    class _FakeLog:
        def error(self, message: str, *_args: object) -> None:
            errors.append(message)

        def info(self, *_args: object, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(main_mod, "log", _FakeLog())
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        main_mod._warn_on_ephemeral_db(_stub_engine("postgresql"))
        assert errors == []
        main_mod._warn_on_ephemeral_db(_stub_engine("sqlite"))
        assert len(errors) == 1
        assert "ephemeral" in errors[0]
    finally:
        get_settings.cache_clear()


def test_ephemeral_db_warning_embeds_the_redacted_url(monkeypatch) -> None:
    """The boot log is readable by anyone with dashboard access — never echo raw credentials."""
    from app import main as main_mod
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:hunter2@db.example.com/teamledger")
    monkeypatch.setattr(main_mod, "redact_database_url", lambda _url: "redacted-sentinel")
    get_settings.cache_clear()
    try:
        message = main_mod.ephemeral_db_warning(_stub_engine("sqlite"))
    finally:
        get_settings.cache_clear()
    assert message is not None
    assert "redacted-sentinel" in message
    assert "hunter2" not in message


@pytest.mark.parametrize(
    ("url", "secret"),
    [
        ("postgresql://user:hunter2@db.example.com:5432/teamledger", "hunter2"),
        ("postgresql+psycopg://admin:p%40ssw0rd@host/db", "p@ssw0rd"),
    ],
)
def test_redact_database_url_masks_the_password(url: str, secret: str) -> None:
    """Keep the parts an operator needs, drop the part that authenticates them."""
    from app.core.config import redact_database_url

    redacted = redact_database_url(url)
    assert secret not in redacted
    assert "teamledger" in redacted or "db" in redacted


def test_redact_database_url_never_raises() -> None:
    """A malformed URL can still hold a credential, so report it instead of echoing."""
    from app.core.config import redact_database_url

    assert "hunter2" not in redact_database_url("://hunter2")


def test_redact_database_url_leaves_passwordless_urls_alone() -> None:
    """SQLite URLs have no password; redacting must not mangle the path."""
    from app.core.config import redact_database_url

    url = "sqlite:///./storage/teamledger.db"
    assert redact_database_url(url) == url
