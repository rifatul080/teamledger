"""Project + Timeliness settings."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

ProjectKind = Literal["general", "paper"]
VenueKind = Literal["journal", "conference"]
ContribVisibility = Literal["leader_only", "all"]


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("kind in ('general','paper')", name="project_kind_check"),
        CheckConstraint("venue_kind is null or venue_kind in ('journal','conference')", name="project_venue_kind_check"),
        CheckConstraint("contrib_visibility in ('leader_only','all')", name="project_vis_check"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    target_venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    submission_deadline: Mapped[Date | None] = mapped_column(Date, nullable=True)
    contrib_visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="leader_only")
    reviewer_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TimelinessSettings(Base):
    """Per-project timeliness bands, in days. Defaults: 2, 7."""

    __tablename__ = "timeliness_settings"

    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), primary_key=True)
    on_time_band_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # <= due
    mild_band_days: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    medium_band_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    late_mild: Mapped[float] = mapped_column(nullable=False, default=0.9)
    late_medium: Mapped[float] = mapped_column(nullable=False, default=0.75)
    late_severe: Mapped[float] = mapped_column(nullable=False, default=0.5)
