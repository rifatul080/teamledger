"""Score adjustment model — manual ± points on a project for a user."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class ScoreAdjustment(Base, TimestampMixin):
    __tablename__ = "score_adjustments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    delta: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    author_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
