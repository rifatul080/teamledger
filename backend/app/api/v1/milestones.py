"""Milestones endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found
from ...models.goal import Goal
from ...models.milestone import Milestone
from ...models.project import Project
from ...models.user import User
from ...schemas.milestones import MilestoneCreate, MilestoneRead, MilestoneUpdate
from ...services import task_service

router = APIRouter(tags=["milestones"])


def _milestone(db: Session, milestone_id: str) -> Milestone:
    m = db.get(Milestone, milestone_id)
    if m is None:
        raise not_found(code="milestone.not_found")
    return m


@router.post("/milestones", response_model=MilestoneRead, status_code=201)
def create_milestone(
    payload: MilestoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    goal = db.get(Goal, payload.goal_id)
    if goal is None:
        raise not_found(code="goal.not_found")
    proj = db.get(Project, goal.project_id)
    require_role(proj.team_id, db, user.id, role="leader")
    m = task_service.create_milestone(db, goal_id=goal.id, title=payload.title, due_date=payload.due_date)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=goal.project_id,
        action="milestone.create",
        subject_kind="milestone",
        subject_id=m.id,
    )
    db.commit()
    return MilestoneRead(
        id=m.id, goal_id=m.goal_id, title=m.title, due_date=m.due_date,
        progress_pct=task_service.milestone_progress(db, m),
    )


@router.get("/milestones/{milestone_id}", response_model=MilestoneRead)
def get_milestone(
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    m = _milestone(db, milestone_id)
    goal = db.get(Goal, m.goal_id)
    proj = db.get(Project, goal.project_id)
    require_membership(proj.team_id, db, user.id)
    return MilestoneRead(
        id=m.id, goal_id=m.goal_id, title=m.title, due_date=m.due_date,
        progress_pct=task_service.milestone_progress(db, m),
    )


@router.patch("/milestones/{milestone_id}", response_model=MilestoneRead)
def update_milestone(
    milestone_id: str,
    payload: MilestoneUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    m = _milestone(db, milestone_id)
    goal = db.get(Goal, m.goal_id)
    proj = db.get(Project, goal.project_id)
    require_role(proj.team_id, db, user.id, role="leader")
    task_service.update_milestone(db, m, title=payload.title, due_date=payload.due_date)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=goal.project_id,
        action="milestone.update",
        subject_kind="milestone",
        subject_id=m.id,
    )
    db.commit()
    return MilestoneRead(
        id=m.id, goal_id=m.goal_id, title=m.title, due_date=m.due_date,
        progress_pct=task_service.milestone_progress(db, m),
    )
