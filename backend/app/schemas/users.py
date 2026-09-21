"""User profile schemas."""
from __future__ import annotations

from pydantic import Field

from .common import ORMModel


class ProfileUpdate(ORMModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = None
    email_delivery_enabled: bool | None = None
