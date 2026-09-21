"""Project, participants, CRediT and timeliness services."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..core.errors import not_found, validation
from ..core.ids import new_id
from ..models.credit import CategoryMultiplier, CRediTCategory
from ..models.membership import Membership
from ..models.participant import ProjectParticipant
from ..models.project import Project, TimelinessSettings
from ..models.score_adjustment import ScoreAdjustment
from ..models.team import Team
from ..models.user import User
from . import credit as credit_service


def _validate_kind(payload: dict) -> None:
    if payload.get("kind") == "paper":
        if not payload.get("target_venue"):
            raise validation("Paper projects need target_venue.", details={"field": "target_venue"})
        if payload.get("venue_kind") not in ("journal", "conference"):
            raise validation("Paper projects need venue_kind.", details={"field": "venue_kind"})
    if payload.get("venue_kind") and payload.get("kind") != "paper":
        raise validation("venue_kind only valid for paper projects.")


def create_project(
    db: Session,
    *,
    team: Team,
    actor: User,
    kind: str,
    name: str,
    description: str | None,
    target_venue: str | None,
    venue_kind: str | None,
    submission_deadline,
    contrib_visibility: str,
    reviewer_user_id: str | None,
    participant_user_ids: list[str],
) -> Project:
    payload = {
        "kind": kind,
        "target_venue": target_venue,
        "venue_kind": venue_kind,
    }
    _validate_kind(payload)
    now = datetime.now(tz=UTC)
    project = Project(
        id=new_id(),
        team_id=team.id,
        kind=kind,
        name=name.strip(),
        description=description,
        target_venue=target_venue,
        venue_kind=venue_kind,
        submission_deadline=submission_deadline,
        contrib_visibility=contrib_visibility,
        reviewer_user_id=reviewer_user_id,
        archived=False,
        created_at=now,
    )
    db.add(project)
    db.flush()
    db.add(TimelinessSettings(project_id=project.id))
    db.flush()
    # Participants must be current team members.
    if participant_user_ids:
        current_members = {
            row[0]
            for row in db.query(Membership.user_id)
            .filter(
                Membership.team_id == team.id,
                Membership.removed_at.is_(None),
                Membership.user_id.in_(participant_user_ids),
            )
            .all()
        }
        for uid in participant_user_ids:
            if uid not in current_members:
                raise validation(
                    f"User {uid} is not a current member of the team.",
                    details={"user_id": uid},
                )
            db.add(ProjectParticipant(id=new_id(), project_id=project.id, user_id=uid, created_at=now))
    db.flush()
    return project


def update_project(db: Session, project: Project, **fields) -> Project:
    payload = {
        "kind": fields.get("kind", project.kind),
        "target_venue": fields.get("target_venue", project.target_venue),
        "venue_kind": fields.get("venue_kind", project.venue_kind),
    }
    _validate_kind(payload)
    for key, val in fields.items():
        if val is not None and hasattr(project, key):
            setattr(project, key, val)
    db.flush()
    return project


def archive_project(db: Session, project: Project) -> None:
    project.archived = True


def set_participants(db: Session, project: Project, user_ids: list[str]) -> None:
    db.query(ProjectParticipant).filter(ProjectParticipant.project_id == project.id).delete()
    now = datetime.now(tz=UTC)
    for uid in user_ids:
        db.add(ProjectParticipant(id=new_id(), project_id=project.id, user_id=uid, created_at=now))
    db.flush()


def is_participant(db: Session, project_id: str, user_id: str) -> bool:
    return (
        db.query(ProjectParticipant)
        .filter(ProjectParticipant.project_id == project_id, ProjectParticipant.user_id == user_id)
        .one_or_none()
        is not None
    )


def participating_user_ids(db: Session, project_id: str) -> list[str]:
    rows = (
        db.query(ProjectParticipant.user_id)
        .filter(ProjectParticipant.project_id == project_id)
        .all()
    )
    return [r[0] for r in rows]


def list_categories() -> list[CRediTCategory]:
    # Source-of-truth list (db also has it; we serve from the constant for speed)
    from ..db.session import get_sessionmaker

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        return list(db.query(CRediTCategory).order_by(CRediTCategory.code).all())


def get_or_create_category(db: Session, code: str) -> CRediTCategory:
    if not credit_service.is_valid_category(code):
        raise validation(f"Unknown CRediT category: {code}", code="credit.invalid")
    cat = db.get(CRediTCategory, code)
    if cat is None:
        cat = CRediTCategory(code=code, label=credit_service.CREDIT_BY_CODE[code])
        db.add(cat)
        db.flush()
    return cat


def set_category_multiplier(db: Session, project_id: str, code: str, multiplier: Decimal) -> CategoryMultiplier:
    get_or_create_category(db, code)
    row = (
        db.query(CategoryMultiplier)
        .filter(CategoryMultiplier.project_id == project_id, CategoryMultiplier.category_code == code)
        .one_or_none()
    )
    if row is None:
        row = CategoryMultiplier(
            id=new_id(),
            project_id=project_id,
            category_code=code,
            multiplier=multiplier,
            created_at=datetime.now(tz=UTC),
        )
        db.add(row)
    else:
        row.multiplier = multiplier
    db.flush()
    return row


def get_category_multipliers(db: Session, project_id: str) -> dict[str, Decimal]:
    rows = (
        db.query(CategoryMultiplier)
        .filter(CategoryMultiplier.project_id == project_id)
        .all()
    )
    return {r.category_code: r.multiplier for r in rows}


def add_score_adjustment(
    db: Session,
    *,
    project: Project,
    user_id: str,
    author: User,
    delta: Decimal,
    reason: str,
) -> ScoreAdjustment:
    row = ScoreAdjustment(
        id=new_id(),
        project_id=project.id,
        user_id=user_id,
        delta=delta,
        reason=reason,
        author_user_id=author.id,
        created_at=datetime.now(tz=UTC),
    )
    db.add(row)
    db.flush()
    return row


def list_score_adjustments(db: Session, project_id: str) -> list[ScoreAdjustment]:
    return (
        db.query(ScoreAdjustment)
        .filter(ScoreAdjustment.project_id == project_id)
        .order_by(ScoreAdjustment.created_at.asc())
        .all()
    )


def get_timeliness(db: Session, project_id: str) -> TimelinessSettings:
    row = db.get(TimelinessSettings, project_id)
    if row is None:
        raise not_found()
    return row


def update_timeliness(
    db: Session,
    project_id: str,
    *,
    on_time_band_days: int | None = None,
    mild_band_days: int | None = None,
    medium_band_days: int | None = None,
    late_mild: Decimal | None = None,
    late_medium: Decimal | None = None,
    late_severe: Decimal | None = None,
) -> TimelinessSettings:
    row = db.get(TimelinessSettings, project_id)
    if row is None:
        raise not_found()
    if on_time_band_days is not None:
        row.on_time_band_days = on_time_band_days
    if mild_band_days is not None:
        row.mild_band_days = mild_band_days
    if medium_band_days is not None:
        row.medium_band_days = medium_band_days
    if late_mild is not None:
        row.late_mild = late_mild
    if late_medium is not None:
        row.late_medium = late_medium
    if late_severe is not None:
        row.late_severe = late_severe
    if not (0 <= row.mild_band_days <= row.medium_band_days):
        raise validation("Band days must be monotone increasing.")
    if not (0 <= row.late_severe <= row.late_medium <= row.late_mild <= 1):
        raise validation("Late multipliers must be in [0, 1] and monotone non-increasing.")
    db.flush()
    return row
