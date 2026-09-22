"""Application settings loaded from environment via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = Field(default="development")
    secret_key: str = Field(default="dev-secret-change-me")
    database_url: str = Field(default="sqlite:///./storage/teamledger.db")
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

    # Public URL the mailer uses to build verification / reset links.
    public_base_url: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
