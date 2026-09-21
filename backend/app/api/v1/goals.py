"""Goals endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found, validation
from ...models.goal import Goal
from ...models.milestone import Milestone
from ...models.project import Project
from ...models.user import User
from ...schemas.goals import GoalCreate, GoalRead, GoalUpdate
from ...schemas.milestones import MilestoneCreate, MilestoneRead, MilestoneUpdate
from ...services import task_service

router = APIRouter(tags=["goals"])


def _ensure_goal_access(db: Session, goal_id: str, user: User, leader_only: bool = False) -> Goal:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise not_found(code="goal.not_found")
    proj = db.get(Project, goal.project_id)
    if proj is None:
        raise not_found(code="project.not_found")
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


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    g = _ensure_goal_access(db, goal_id, user, leader_only=True)
    proj = db.get(Project, g.project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    from ...models.task import Task

    ms_ids = [m.id for m in db.query(Milestone).filter(Milestone.goal_id == g.id).all()]
    if ms_ids:
        has_done = (
            db.query(Task.id)
            .filter(Task.milestone_id.in_(ms_ids), Task.status == "done")
            .first()
        )
        if has_done is not None:
            raise validation(
                "Cannot delete a goal with completed tasks.",
                code="goal.has_done_tasks",
            )
    db.delete(g)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=g.project_id,
        action="goal.delete",
        subject_kind="goal",
        subject_id=goal_id,
    )
    db.commit()


@router.get("/projects/{project_id}/goals", response_model=list[GoalRead])
def list_goals(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[GoalRead]:
    proj = db.get(Project, project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    require_membership(proj.team_id, db, user.id)
    rows = (
        db.query(Goal)
        .filter(Goal.project_id == project_id)
        .order_by(Goal.target_date.is_(None), Goal.target_date.asc(), Goal.created_at.asc())
        .all()
    )
    out: list[GoalRead] = []
    for g in rows:
        out.append(
            GoalRead(
                id=g.id,
                project_id=g.project_id,
                title=g.title,
                description=g.description,
                target_date=g.target_date,
                progress_pct=task_service.goal_progress(db, g),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Milestones


def _ensure_milestone_access(db: Session, ms_id: str, user: User, leader_only: bool = False) -> Milestone:
    ms = db.get(Milestone, ms_id)
    if ms is None:
        raise not_found(code="milestone.not_found")
    goal = db.get(Goal, ms.goal_id)
    if goal is None:
        raise not_found(code="goal.not_found")
    proj = db.get(Project, goal.project_id)
    if proj is None:
        raise not_found(code="project.not_found")
    if leader_only:
        require_role(proj.team_id, db, user.id, role="leader")
    else:
        require_membership(proj.team_id, db, user.id)
    return ms


@router.post("/goals/{goal_id}/milestones", response_model=MilestoneRead, status_code=201)
def create_milestone(
    goal_id: str,
    payload: MilestoneCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    g = _ensure_goal_access(db, goal_id, user, leader_only=True)
    proj = db.get(Project, g.project_id)
    m = task_service.create_milestone(
        db,
        goal_id=g.id,
        title=payload.title,
        due_date=payload.due_date,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=g.project_id,
        action="milestone.create",
        subject_kind="milestone",
        subject_id=m.id,
    )
    db.commit()
    return MilestoneRead(
        id=m.id,
        goal_id=m.goal_id,
        title=m.title,
        due_date=m.due_date,
        completed_at=m.completed_at,
        progress_pct=task_service.milestone_progress(db, m),
    )


@router.get("/milestones/{ms_id}", response_model=MilestoneRead)
def get_milestone(
    ms_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    m = _ensure_milestone_access(db, ms_id, user)
    return MilestoneRead(
        id=m.id,
        goal_id=m.goal_id,
        title=m.title,
        due_date=m.due_date,
        completed_at=m.completed_at,
        progress_pct=task_service.milestone_progress(db, m),
    )


@router.patch("/milestones/{ms_id}", response_model=MilestoneRead)
def update_milestone(
    ms_id: str,
    payload: MilestoneUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> MilestoneRead:
    m = _ensure_milestone_access(db, ms_id, user, leader_only=True)
    task_service.update_milestone(db, m, title=payload.title, due_date=payload.due_date)
    if payload.complete and m.completed_at is None:
        m.completed_at = datetime.now(tz=UTC)
    elif not payload.complete and m.completed_at is not None:
        m.completed_at = None
    db.commit()
    return MilestoneRead(
        id=m.id,
        goal_id=m.goal_id,
        title=m.title,
        due_date=m.due_date,
        completed_at=m.completed_at,
        progress_pct=task_service.milestone_progress(db, m),
    )


@router.delete("/milestones/{ms_id}", status_code=204)
def delete_milestone(
    ms_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    m = _ensure_milestone_access(db, ms_id, user, leader_only=True)
    from ...models.task import Task

    has_done = (
        db.query(Task.id)
        .filter(Task.milestone_id == m.id, Task.status == "done")
        .first()
    )
    if has_done is not None:
        raise validation(
            "Cannot delete a milestone with completed tasks.",
            code="milestone.has_done_tasks",
        )
    goal = db.get(Goal, m.goal_id)
    proj = db.get(Project, goal.project_id)
    db.delete(m)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=goal.project_id,
        action="milestone.delete",
        subject_kind="milestone",
        subject_id=ms_id,
    )
    db.commit()


@router.get("/goals/{goal_id}/milestones", response_model=list[MilestoneRead])
def list_milestones(
    goal_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[MilestoneRead]:
    _ensure_goal_access(db, goal_id, user)
    rows = (
        db.query(Milestone)
        .filter(Milestone.goal_id == goal_id)
        .order_by(Milestone.due_date.is_(None), Milestone.due_date.asc(), Milestone.created_at.asc())
        .all()
    )
    out: list[MilestoneRead] = []
    for m in rows:
        out.append(
            MilestoneRead(
                id=m.id,
                goal_id=m.goal_id,
                title=m.title,
                due_date=m.due_date,
                completed_at=m.completed_at,
                progress_pct=task_service.milestone_progress(db, m),
            )
        )
    return out
