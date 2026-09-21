"""Tasks endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import forbidden, not_found, validation
from ...models.goal import Goal
from ...models.milestone import Milestone
from ...models.project import Project
from ...models.task import Task
from ...models.user import User
from ...schemas.tasks import (
    TaskCreate,
    TaskPropose,
    TaskRead,
    TaskReview,
    TaskSplit,
    TaskSubmit,
    TaskUpdate,
)
from ...services import project_service, task_service

router = APIRouter(tags=["tasks"])


def _get_task(db: Session, task_id: str) -> Task:
    t = db.get(Task, task_id)
    if t is None:
        raise not_found(code="task.not_found")
    return t


def _project_of_task(db: Session, task: Task) -> Project:
    ms = db.get(Milestone, task.milestone_id)
    if ms is None:
        raise not_found()
    g = db.get(Goal, ms.goal_id)
    return db.get(Project, g.project_id)


@router.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    ms = db.get(Milestone, payload.milestone_id)
    if ms is None:
        raise not_found(code="milestone.not_found")
    goal = db.get(Goal, ms.goal_id)
    proj = db.get(Project, goal.project_id)
    require_role(proj.team_id, db, user.id, role="leader")
    assignee = db.get(User, payload.assignee_user_id)
    if assignee is None:
        raise not_found(code="user.not_found")
    if not project_service.is_participant(db, proj.id, assignee.id):
        raise validation(
            "Assignee must be a project participant.",
            code="task.assignee_not_participant",
        )
    t = task_service.create_task(
        db,
        milestone_id=ms.id,
        assignee=assignee,
        actor=user,
        title=payload.title,
        description=payload.description,
        category_code=payload.category_code,
        weight=payload.weight,
        est_hours=payload.est_hours,
        start_date=payload.start_date,
        due_date=payload.due_date,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.create",
        subject_kind="task",
        subject_id=t.id,
        payload={"assignee": t.assignee_user_id},
    )
    db.commit()
    return TaskRead.model_validate(t)


@router.post("/tasks/propose", response_model=TaskRead, status_code=201)
def propose_task(
    payload: TaskPropose,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    ms = db.get(Milestone, payload.milestone_id)
    if ms is None:
        raise not_found(code="milestone.not_found")
    goal = db.get(Goal, ms.goal_id)
    proj = db.get(Project, goal.project_id)
    require_membership(proj.team_id, db, user.id)
    t = task_service.propose_task(
        db,
        milestone_id=ms.id,
        proposer=user,
        title=payload.title,
        description=payload.description,
        category_code=payload.category_code,
        weight=payload.weight,
        est_hours=payload.est_hours,
        start_date=payload.start_date,
        due_date=payload.due_date,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.propose",
        subject_kind="task",
        subject_id=t.id,
    )
    db.commit()
    return TaskRead.model_validate(t)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    require_membership(proj.team_id, db, user.id)
    return TaskRead.model_validate(t)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    membership = require_membership(proj.team_id, db, user.id)
    # Members can only update status (not weight/assignee); leader can update all.
    is_leader_role = membership.role == "leader"
    if not is_leader_role:
        if any(
            getattr(payload, f) is not None
            for f in (
                "assignee_user_id",
                "category_code",
                "weight",
                "est_hours",
                "start_date",
                "due_date",
                "title",
                "description",
            )
        ):
            raise forbidden(code="task.member_readonly", message="Only the leader can change task details.")
        if t.assignee_user_id != user.id and payload.status is not None:
            # members can only update status of their own tasks.
            raise forbidden(code="task.not_assignee")
    task_service.update_task(
        db,
        t,
        actor=user,
        title=payload.title,
        description=payload.description,
        assignee_user_id=payload.assignee_user_id,
        category_code=payload.category_code,
        weight=payload.weight,
        est_hours=payload.est_hours,
        start_date=payload.start_date,
        due_date=payload.due_date,
        status=payload.status,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.update",
        subject_kind="task",
        subject_id=t.id,
    )
    db.commit()
    return TaskRead.model_validate(t)


@router.post("/tasks/{task_id}/split", response_model=TaskRead, status_code=201)
def split_task(
    task_id: str,
    payload: TaskSplit,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    require_role(proj.team_id, db, user.id, role="leader")
    new_assignee = db.get(User, payload.new_assignee_user_id)
    if new_assignee is None:
        raise not_found(code="user.not_found")
    new_t = task_service.split_task(
        db,
        task=t,
        actor=user,
        new_assignee=new_assignee,
        weight=payload.weight,
        est_hours=payload.est_hours,
        category_code=payload.category_code,
        title=payload.title,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.split",
        subject_kind="task",
        subject_id=t.id,
        payload={"new_task_id": new_t.id},
    )
    db.commit()
    return TaskRead.model_validate(new_t)


@router.post("/tasks/{task_id}/submit", response_model=TaskRead)
def submit(
    task_id: str,
    payload: TaskSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    require_membership(proj.team_id, db, user.id)
    if t.assignee_user_id != user.id and not _is_leader_for(db, proj, user):
        raise forbidden(code="task.submit_assignee_only")
    task_service.submit_for_review(db, task=t, actor=user, note=payload.note)
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.submit",
        subject_kind="task",
        subject_id=t.id,
    )
    db.commit()
    return TaskRead.model_validate(t)


@router.post("/tasks/{task_id}/review", response_model=TaskRead)
def review(
    task_id: str,
    payload: TaskReview,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:

    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    ms = db.get(Milestone, t.milestone_id)
    _ = db.get(Goal, ms.goal_id)
    _ = require_membership(proj.team_id, db, user.id)
    m = require_membership(proj.team_id, db, user.id)
    # Reviewer must be the project reviewer (or leader if no project reviewer).
    allowed = m.role == "leader" or (
        proj.reviewer_user_id is not None and proj.reviewer_user_id == user.id
    )
    if not allowed:
        raise forbidden(code="review.not_reviewer", message="Only the reviewer can review this task.")
    task_service.review_task(
        db,
        task=t,
        reviewer=user,
        decision=payload.decision,
        quality=payload.quality,
        note=payload.note,
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=proj.team_id,
        project_id=proj.id,
        action="task.review",
        subject_kind="task",
        subject_id=t.id,
        payload={"decision": payload.decision, "quality": payload.quality},
    )
    db.commit()
    return TaskRead.model_validate(t)


@router.post("/tasks/{task_id}/approve-proposal", response_model=TaskRead)
def approve_proposal(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TaskRead:
    t = _get_task(db, task_id)
    proj = _project_of_task(db, t)
    require_role(proj.team_id, db, user.id, role="leader")
    task_service.approve_proposed_task(db, task=t, assignee=(t.assignee and db.get(User, t.assignee_user_id)) or user, actor=user)
    db.commit()
    return TaskRead.model_validate(t)


def _is_leader_for(db: Session, project: Project, user: User) -> bool:
    from ...models.membership import Membership

    m = (
        db.query(Membership)
        .filter(
            Membership.team_id == project.team_id,
            Membership.user_id == user.id,
            Membership.removed_at.is_(None),
        )
        .one_or_none()
    )
    return m is not None and m.role == "leader"


@router.get("/milestones/{milestone_id}/tasks", response_model=list[TaskRead])
def list_tasks(
    milestone_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[TaskRead]:
    ms = db.get(Milestone, milestone_id)
    if ms is None:
        raise not_found(code="milestone.not_found")
    g = db.get(Goal, ms.goal_id)
    proj = db.get(Project, g.project_id)
    require_membership(proj.team_id, db, user.id)
    rows = db.query(Task).filter(Task.milestone_id == milestone_id).all()
    return [TaskRead.model_validate(t) for t in rows]
