"""Projects endpoints."""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found, validation
from ...models.project import Project
from ...models.user import User
from ...schemas.projects import (
    CategoryMultiplierIn,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ScoreAdjustmentCreate,
    ScoreAdjustmentRead,
)
from ...schemas.scoring import ScoreRead
from ...services import project_service, task_service
from ...services.credit import CREDIT_BY_CODE

router = APIRouter(tags=["projects"])


@router.get("/credit-categories", response_model=list[dict])
def list_categories_route(_: User = Depends(current_user)) -> list[dict]:
    return [{"code": c, "label": label} for c, label in CREDIT_BY_CODE.items()]


@router.post(
    "/teams/{team_id}/projects",
    response_model=ProjectRead,
    status_code=201,
)
def create_project(
    payload: ProjectCreate,
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ProjectRead:
    require_role(team_id, db, user.id, role="leader")
    proj = project_service.create_project(
        db,
        team=db.get(Project, team_id) or _team(db, team_id),
        actor=user,
        kind=payload.kind,
        name=payload.name,
        description=payload.description,
        target_venue=payload.target_venue,
        venue_kind=payload.venue_kind,
        submission_deadline=payload.submission_deadline,
        contrib_visibility=payload.contrib_visibility,
        reviewer_user_id=payload.reviewer_user_id,
        participant_user_ids=payload.participant_user_ids,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=team_id,
        project_id=proj.id,
        action="project.create",
        subject_kind="project",
        subject_id=proj.id,
        payload={"kind": proj.kind, "name": proj.name},
    )
    db.commit()
    return ProjectRead.model_validate(proj)


def _team(db: Session, team_id: str):
    from ...models.team import Team

    return db.get(Team, team_id)


@router.get("/teams/{team_id}/projects", response_model=list[ProjectRead])
def list_projects(
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ProjectRead]:
    require_membership(team_id, db, user.id)
    rows = db.query(Project).filter(Project.team_id == team_id).order_by(Project.created_at.desc()).all()
    return [ProjectRead.model_validate(p) for p in rows]


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ProjectRead:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_membership(proj.team_id, db, user.id)
    return ProjectRead.model_validate(proj)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    payload: ProjectUpdate,
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ProjectRead:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    if proj.archived:
        raise validation("Project is archived.", code="project.archived")
    project_service.update_project(
        db,
        proj,
        kind=payload.kind,
        name=payload.name,
        description=payload.description,
        target_venue=payload.target_venue,
        venue_kind=payload.venue_kind,
        submission_deadline=payload.submission_deadline,
        contrib_visibility=payload.contrib_visibility,
        reviewer_user_id=payload.reviewer_user_id,
        archived=payload.archived,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="project.update",
        subject_kind="project",
        subject_id=proj.id,
    )
    db.commit()
    return ProjectRead.model_validate(proj)


@router.post("/projects/{project_id}/participants", status_code=204)
def set_participants(
    project_id: str,
    user_ids: list[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    project_service.set_participants(db, proj, user_ids)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="project.set_participants",
        subject_kind="project",
        subject_id=proj.id,
        payload={"count": len(user_ids)},
    )
    db.commit()


@router.put("/projects/{project_id}/multipliers", response_model=list[CategoryMultiplierIn])
def upsert_multiplier(
    project_id: str,
    payload: list[CategoryMultiplierIn],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CategoryMultiplierIn]:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    out: list[CategoryMultiplierIn] = []
    for m in payload:
        row = project_service.set_category_multiplier(
            db, project_id, m.category_code, Decimal(str(m.multiplier))
        )
        out.append(CategoryMultiplierIn(category_code=row.category_code, multiplier=Decimal(str(row.multiplier))))
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="project.multipliers_update",
        subject_kind="project",
        subject_id=proj.id,
    )
    db.commit()
    return out


@router.get("/projects/{project_id}/multipliers", response_model=list[CategoryMultiplierIn])
def list_multipliers(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CategoryMultiplierIn]:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_membership(proj.team_id, db, user.id)
    cats = project_service.get_category_multipliers(db, project_id)
    return [
        CategoryMultiplierIn(category_code=c, multiplier=Decimal(str(m)))
        for c, m in cats.items()
    ]


@router.get(
    "/projects/{project_id}/timeliness",
    response_model=dict,
)
def get_timeliness(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    ts = project_service.get_timeliness(db, project_id)
    return {
        "on_time_band_days": ts.on_time_band_days,
        "mild_band_days": ts.mild_band_days,
        "medium_band_days": ts.medium_band_days,
        "late_mild": str(ts.late_mild),
        "late_medium": str(ts.late_medium),
        "late_severe": str(ts.late_severe),
    }


@router.put(
    "/projects/{project_id}/timeliness",
    response_model=dict,
)
def update_timeliness(
    project_id: str,
    on_time_band_days: int | None = None,
    mild_band_days: int | None = None,
    medium_band_days: int | None = None,
    late_mild: Decimal | None = None,
    late_medium: Decimal | None = None,
    late_severe: Decimal | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    project_service.update_timeliness(
        db,
        project_id,
        on_time_band_days=on_time_band_days,
        mild_band_days=mild_band_days,
        medium_band_days=medium_band_days,
        late_mild=late_mild,
        late_medium=late_medium,
        late_severe=late_severe,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="project.timeliness_update",
        subject_kind="project",
        subject_id=proj.id,
    )
    db.commit()
    return get_timeliness(project_id=project_id, db=db, user=user)


@router.post(
    "/projects/{project_id}/adjustments",
    response_model=ScoreAdjustmentRead,
    status_code=201,
)
def add_adjustment(
    project_id: str,
    payload: ScoreAdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ScoreAdjustmentRead:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    row = project_service.add_score_adjustment(
        db,
        project=proj,
        user_id=payload.user_id,
        author=user,
        delta=Decimal(str(payload.delta)),
        reason=payload.reason,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="score.adjustment_add",
        subject_kind="user",
        subject_id=payload.user_id,
        payload={"delta": str(row.delta), "reason": row.reason},
    )
    db.commit()
    return ScoreAdjustmentRead.model_validate(row)


@router.get(
    "/projects/{project_id}/adjustments",
    response_model=list[ScoreAdjustmentRead],
)
def list_adjustments(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[ScoreAdjustmentRead]:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_membership(proj.team_id, db, user.id)
    rows = project_service.list_score_adjustments(db, project_id)
    return [ScoreAdjustmentRead.model_validate(r) for r in rows]


@router.get(
    "/projects/{project_id}/score",
    response_model=ScoreRead,
)
def get_score(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ScoreRead:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_membership(proj.team_id, db, user.id)
    if proj.contrib_visibility == "leader_only":
        require_role(proj.team_id, db, user.id, role="leader")

    result = task_service.compute_score(db, project_id)

    def _to_task(t):
        return {
            "task_id": t.task_id,
            "assignee_user_id": t.assignee_user_id,
            "category_code": t.category_code,
            "weight": t.weight,
            "quality": t.quality,
            "days_late": t.days_late,
            "timeliness": str(t.timeliness),
            "category_multiplier": str(t.category_multiplier),
            "points": str(t.points),
        }

    out_participants = []
    for p in result.participants:
        out_participants.append(
            {
                "user_id": p.user_id,
                "display_name": p.display_name,
                "total_points": str(p.total_points),
                "share_pct": str(p.share_pct),
                "by_category": {k: str(v) for k, v in p.by_category.items()},
                "tasks": [_to_task(t) for t in p.tasks],
                "adjustments": [
                    {
                        "delta": str(a.delta),
                        "reason": a.reason,
                        "author_user_id": a.author_user_id,
                        "created_at": a.created_at,
                    }
                    for a in p.adjustments
                ],
            }
        )
    return {
        "project_id": result.project_id,
        "formula_version": result.formula_version,
        "total_points": str(result.total_points),
        "participants": out_participants,
        "suggested_order": [
            {"position": o.position, "user_id": o.user_id, "suggested": o.suggested, "note": o.note}
            for o in result.suggested_order
        ],
        "final_order": (
            [
                {"position": o.position, "user_id": o.user_id, "suggested": o.suggested, "note": o.note}
                for o in result.final_order
            ]
            if result.final_order is not None
            else None
        ),
    }
