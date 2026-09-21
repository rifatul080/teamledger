"""SQLAlchemy 2 declarative base."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    type_annotation_map: ClassVar[dict[type[Any], Any]] = {datetime: DateTime(timezone=True)}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(tz=UTC),
    )


@event.listens_for(Session, "before_flush")
def _ensure_created_at(session: Session, flush_context: Any, instances: Any) -> None:
    """Fill in created_at on insert if the caller forgot."""
    for obj in session.new:
        if isinstance(obj, TimestampMixin) and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(tz=UTC)


def jsonable(value: Any) -> Any:
    """Helper to coerce common DB values to JSON-friendly Python."""
    if isinstance(value, datetime):
        return value.isoformat()
    return value
