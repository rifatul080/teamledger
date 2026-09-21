"""Project schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from .common import ORMModel

ProjectKind = Literal["general", "paper"]
VenueKind = Literal["journal", "conference"]
ContribVisibility = Literal["leader_only", "all"]


class ProjectCreate(ORMModel):
    kind: ProjectKind = "general"
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_venue: str | None = None
    venue_kind: VenueKind | None = None
    submission_deadline: date | None = None
    contrib_visibility: ContribVisibility = "leader_only"
    reviewer_user_id: str | None = None
    participant_user_ids: list[str] = Field(default_factory=list)


class ProjectUpdate(ORMModel):
    name: str | None = None
    description: str | None = None
    target_venue: str | None = None
    venue_kind: VenueKind | None = None
    submission_deadline: date | None = None
    contrib_visibility: ContribVisibility | None = None
    reviewer_user_id: str | None = None
    archived: bool | None = None


class ProjectRead(ORMModel):
    id: str
    team_id: str
    kind: ProjectKind
    name: str
    description: str | None
    target_venue: str | None
    venue_kind: VenueKind | None
    submission_deadline: date | None
    contrib_visibility: ContribVisibility
    reviewer_user_id: str | None
    finalized_at: datetime | None
    archived: bool
    created_at: datetime


class CategoryMultiplierIn(ORMModel):
    category_code: str
    multiplier: Decimal = Field(ge=Decimal("0"), le=Decimal("5"))


class ScoreAdjustmentCreate(ORMModel):
    user_id: str
    delta: Decimal
    reason: str = Field(min_length=1, max_length=2000)


class ScoreAdjustmentRead(ORMModel):
    id: str
    project_id: str
    user_id: str
    delta: Decimal
    reason: str
    author_user_id: str
    created_at: datetime
