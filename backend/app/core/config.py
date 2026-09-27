"""Application settings loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Rewrite bare ``postgresql://`` URLs to use the psycopg v3 driver.

    SQLAlchemy defaults to psycopg2 when the URL has no driver prefix. We
    ship both psycopg v3 and psycopg2-binary; prefer v3 when the caller
    didn't specify a driver, so a bare ``postgresql://...`` from Railway,
    Neon, Render, etc. works without thinking about prefixes.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


def redact_database_url(url: str) -> str:
    """Return ``url`` with its password masked, so it is safe to log.

    Startup diagnostics need to name the database they are complaining
    about, but ``DATABASE_URL`` routinely carries a password and Render
    prints the boot log to anyone with dashboard access. Masking keeps the
    useful part (driver, host, database name) and drops the secret.

    Never raises: an unparsable URL is reported as such rather than echoed,
    since a malformed value can still contain a credential.
    """
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<unparsable database url>"


class Settings(BaseSettings):
    """Settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = Field(default="development")
    secret_key: str = Field(default="dev-secret-change-me")
    database_url: str = Field(default="sqlite:///./storage/teamledger.db")

    @field_validator("database_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return _normalize_database_url(value)
    redis_url: str = Field(default="redis://localhost:6379/0")

    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 14
    password_reset_ttl_min: int = 30
    invite_ttl_days: int = 7
    login_rate_limit_per_min: int = 10
    reset_rate_limit_per_min: int = 5
    signup_rate_limit_per_min: int = 5

    # v2 — real email provider (Resend by default; falls back to console).
    resend_api_key: str = ""
    resend_from: str = "TeamLedger <noreply@teamledger.app>"
    # Avatar storage location (sibling of file storage root by default).
    avatar_local_root: str = "./storage/avatars"
    avatar_max_bytes: int = 4 * 1024 * 1024  # 4 MiB cap

    storage_backend: Literal["local"] = "local"
    storage_local_root: str = "./storage/files"
    file_max_bytes: int = 100 * 1024 * 1024

    cors_allowed_origins: str = "http://localhost:5173"

    mail_backend: Literal["console", "smtp", "resend"] = "console"
    mail_from: str = "teamledger@example.org"
    smtp_host: str = "maildev"
    smtp_port: int = 1025

    ws_heartbeat_seconds: int = 25

    default_timezone: str = "UTC"

    # Cookie SameSite. Defaults to "lax" so the same-origin mono-host
    # deploy (Render / Fly.io serving API + SPA from one origin) keeps
    # working without changes. Set to "none" when the frontend is on a
    # different origin than the API (Vercel + Render split deploy).
    # "none" requires Secure=True — we force that automatically when this
    # is "none".
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Public URL the mailer uses to build verification / reset links.
    public_base_url: str = "http://localhost:5173"

    # Social sign-in (OAuth 2.0 authorization-code flow). Leave the client id
    # empty to keep a provider disabled — the UI hides buttons for providers
    # that /auth/oauth/providers reports as unconfigured.
    google_client_id: str = ""
    google_client_secret: str = ""
    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    # Origin that serves the API (the redirect URI is built from it). Defaults
    # to public_base_url, which is correct for same-origin deploys.
    oauth_redirect_base: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
