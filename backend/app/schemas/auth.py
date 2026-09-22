"""Auth request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from .common import ORMModel


class SignupRequest(ORMModel):
    email: EmailStr
    password: str = Field(min_length=10)
    display_name: str = Field(min_length=1, max_length=120)
    timezone: str = "UTC"
    institution: str | None = Field(default=None, max_length=255)
    institution_hint: str | None = Field(default=None, max_length=255)


class LoginRequest(ORMModel):
    email: EmailStr
    password: str


class RefreshRequest(ORMModel):
    refresh_token: str | None = None  # can also come from cookie


class AccessTokenResponse(ORMModel):
    access_token: str
    csrf_token: str
    expires_in: int


class LogoutRequest(ORMModel):
    refresh_token: str | None = None


class PasswordResetRequest(ORMModel):
    email: EmailStr


class PasswordResetConfirm(ORMModel):
    token: str
    new_password: str = Field(min_length=10)


class VerifyEmailRequest(ORMModel):
    token: str


class UserPublic(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    timezone: str
    created_at: datetime
    email_verified: bool = False
    avatar_url: str | None = None
    avatar_url_small: str | None = None
    avatar_url_large: str | None = None
    theme: str = "light"
    institution: str | None = None


class ProfileUpdate(ORMModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    theme: str | None = Field(default=None, pattern=r"^(light|dark)$")
    institution: str | None = Field(default=None, max_length=255)


class InstitutionHint(ORMModel):
    """Returned by /auth/institution-hint?email=... — best-effort prefill."""

    hint: str | None = None
