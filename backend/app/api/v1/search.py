"""v2 — Global search across messages, tasks, files (one box, grouped results).

Authorized at the same level as the rest of the API; results are scoped to
the teams the caller belongs to (current memberships).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db
from ...core.errors import validation
from ...models.file import FileEntry
from ...models.membership import Membership
from ...models.message import ChatMessage
from ...models.task import Task

router = APIRouter()


def _caller_team_ids(db: Session, user_id: str) -> list[str]:
    return [
        m.team_id
        for m in db.query(Membership).filter(Membership.user_id == user_id).all()
    ]


@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user=Depends(current_user),
) -> dict:
    term = q.strip()
    if not term:
        raise validation("q is required.")
    team_ids = _caller_team_ids(db, user.id)
    if not team_ids:
        return {"tasks": [], "messages": [], "files": []}

    # Tasks: search by title (members may not see every project column; we
    # stay loose by joining on the project/goal/milestone chain).
    from ...models.goal import Goal
    from ...models.milestone import Milestone
    from ...models.project import Project

    proj_ids = [p.id for p in db.query(Project).filter(Project.team_id.in_(team_ids)).all()]
    goal_ids = [
        g.id
        for g in db.query(Goal).filter(Goal.project_id.in_(proj_ids)).all()
        if proj_ids
    ]
    milestone_ids = (
        [m.id for m in db.query(Milestone).filter(Milestone.goal_id.in_(goal_ids)).all()]
        if goal_ids
        else []
    )
    tasks: list[dict] = []
    if milestone_ids:
        like = f"%{term}%"
        ts = (
            db.query(Task)
            .filter(Task.milestone_id.in_(milestone_ids), Task.title.ilike(like))
            .order_by(Task.due_date.asc().nullslast())
            .limit(limit)
            .all()
        )
        for t in ts:
            ms = db.get(Milestone, t.milestone_id)
            goal = db.get(Goal, ms.goal_id) if ms else None
            proj = db.get(Project, goal.project_id) if goal else None
            tasks.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "project_id": proj.id if proj else "",
                    "status": t.status,
                }
            )

    # Messages: text search over body.
    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.team_id.in_(team_ids), ChatMessage.body.ilike(f"%{term}%"), ChatMessage.deleted_at.is_(None))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    messages = [{"id": m.id, "body": m.body, "team_id": m.team_id} for m in msgs]

    # Files: name match.
    file_rows = (
        db.query(FileEntry)
        .filter(FileEntry.team_id.in_(team_ids), FileEntry.name.ilike(f"%{term}%"))
        .order_by(FileEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    files = [{"id": f.id, "name": f.name, "team_id": f.team_id} for f in file_rows]

    return {"tasks": tasks, "messages": messages, "files": files}
