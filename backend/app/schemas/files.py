"""File library schemas."""
from __future__ import annotations

from datetime import datetime

from .common import ORMModel


class FileRead(ORMModel):
    id: str
    team_id: str
    folder: str
    name: str
    current_version_no: int
    size_bytes: int
    content_type: str
    sha256: str
    uploader_user_id: str
    updated_at: datetime


class FileVersionRead(ORMModel):
    version_no: int
    size_bytes: int
    content_type: str
    sha256: str
    uploader_user_id: str
    uploaded_at: datetime
    original_name: str
