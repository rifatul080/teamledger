"""File library models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class FileEntry(Base, TimestampMixin):
    """A logical file: name + folder, holds a current version pointer."""

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_file_team_folder_name", "team_id", "folder", "name", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    folder: Mapped[str] = mapped_column(String(120), nullable=False, default="/")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploader_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)


class FileVersion(Base, TimestampMixin):
    __tablename__ = "file_versions"
    __table_args__ = (
        Index("ix_fv_file_version", "file_id", "version_no", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(32), ForeignKey("files.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(nullable=False, default=1)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploader_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
