"""Author order snapshots."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class AuthorOrderSnapshot(Base, TimestampMixin):
    """Immutable snapshot of the finalized author order for a project."""

    __tablename__ = "author_order_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(String(200_000), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_by: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)


class AuthorOrderPosition(Base, TimestampMixin):
    """Per-snapshot position rows for query convenience."""

    __tablename__ = "author_order_positions"
    __table_args__ = (
        # unique (snapshot_id, position) implicit; we just enforce it via app code
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("author_order_snapshots.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
