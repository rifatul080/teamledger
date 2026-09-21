"""Goals endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found, validation
from ...models.goal import Goal
from ...models.project import Project
from ...models.user import User
from ...schemas.goals import GoalCreate, GoalRead, GoalUpdate
from ...services import task_service

router = APIRouter(tags=["goals"])


def _ensure_goal_access(db: Session, goal_id: str, user: User, leader_only: bool = False) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise not_found(code="goal.not_found")
    proj = db.get(Project, goal.project_id)
    if leader_only:
        require_role(proj.team_id, db, user.id, role="leader")
    else:
        require_membership(proj.team_id, db, user.id)
    return goal


@router.post("/goals", response_model=GoalRead, status_code=201)
def create_goal(
    payload: GoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> GoalRead:
    proj = db.get(Project, payload.project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_role(proj.team_id, db, user.id, role="leader")
    if proj.archived:
        raise validation("Project is archived.", code="project.archived")
    g = task_service.create_goal(
        db,
        project_id=proj.id,
        title=payload.title,
        description=payload.description,
        target_date=payload.target_date,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="goal.create",
        subject_kind="goal",
        subject_id=g.id,
    )
    db.commit()
    return GoalRead(
        id=g.id,
        project_id=g.project_id,
        title=g.title,
        description=g.description,
        target_date=g.target_date,
        progress_pct=task_service.goal_progress(db, g),
    )


@router.get("/goals/{goal_id}", response_model=GoalRead)
def get_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> GoalRead:
    g = _ensure_goal_access(db, goal_id, user)
    return GoalRead(
        id=g.id,
        project_id=g.project_id,
        title=g.title,
        description=g.description,
        target_date=g.target_date,
        progress_pct=task_service.goal_progress(db, g),
    )


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: str,
    payload: GoalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> GoalRead:
    g = _ensure_goal_access(db, goal_id, user, leader_only=True)
    task_service.update_goal(
        db, g, title=payload.title, description=payload.description, target_date=payload.target_date
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=db.get(Project, g.project_id).team_id,
        project_id=g.project_id,
        action="goal.update",
        subject_kind="goal",
        subject_id=g.id,
    )
    db.commit()
    return GoalRead(
        id=g.id,
        project_id=g.project_id,
        title=g.title,
        description=g.description,
        target_date=g.target_date,
        progress_pct=task_service.goal_progress(db, g),
    )
