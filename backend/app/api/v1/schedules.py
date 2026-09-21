"""Schedules, calendar, timeline, overload check."""
from __future__ import annotations

from datetime import date as date_t

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import not_found
from ...models.schedule import ScheduleSlot
from ...models.team import Team
from ...models.user import User
from ...schemas.schedules import WeeklyPlanIn, WeeklyPlanRead
from ...services import schedule_service

router = APIRouter(tags=["schedules"])


@router.put("/teams/{team_id}/schedules", response_model=WeeklyPlanRead)
def upsert_plan(
    payload: WeeklyPlanIn,
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> WeeklyPlanRead:
    require_role(team_id, db, user.id, role="leader")
    team = db.get(Team, team_id)
    if team is None:
        raise not_found(code="team.not_found")
    plan = schedule_service.set_plan(
        db,
        team=team,
        user_id=payload.user_id,
        weekly_cap_hours=payload.weekly_cap_hours,
        slots=[s.model_dump() for s in payload.slots],
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=team_id,
        action="schedule.set_plan",
        subject_kind="user",
        subject_id=payload.user_id,
    )
    db.commit()
    return WeeklyPlanRead(
        id=plan.id,
        team_id=plan.team_id,
        user_id=plan.user_id,
        weekly_cap_hours=plan.weekly_cap_hours,
        slots=[
            {"weekday": s.weekday, "start_minute": s.start_minute, "end_minute": s.end_minute}
            for s in db.query(ScheduleSlot).filter(ScheduleSlot.weekly_plan_id == plan.id).all()
        ],
    )


@router.get("/teams/{team_id}/schedules/{user_id}", response_model=WeeklyPlanRead | dict)
def get_plan(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    plan = schedule_service.get_plan(db, team_id=team_id, user_id=user_id)
    if plan is None:
        return {"team_id": team_id, "user_id": user_id, "weekly_cap_hours": 0, "slots": []}
    slots = db.query(ScheduleSlot).filter(ScheduleSlot.weekly_plan_id == plan.id).all()
    return {
        "id": plan.id,
        "team_id": plan.team_id,
        "user_id": plan.user_id,
        "weekly_cap_hours": plan.weekly_cap_hours,
        "slots": [
            {"weekday": s.weekday, "start_minute": s.start_minute, "end_minute": s.end_minute}
            for s in slots
        ],
    }


@router.get("/teams/{team_id}/calendar")
def calendar(
    team_id: str,
    start: date_t = Query(...),
    end: date_t = Query(...),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    return schedule_service.calendar(
        db, team_id=team_id, range_start=start, range_end=end, user_id=user_id
    )


@router.get("/teams/{team_id}/timeline")
def timeline(
    team_id: str,
    start: date_t = Query(...),
    end: date_t = Query(...),
    user_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    return schedule_service.timeline(
        db, team_id=team_id, range_start=start, range_end=end, user_id=user_id
    )


@router.get("/teams/{team_id}/overload")
def overload(
    team_id: str,
    week_start: date_t = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_membership(team_id, db, user.id)
    rows = []
    member_ids = [
        r[0]
        for r in db.query(__import__("app.models.membership", fromlist=["Membership"]).Membership.user_id)
        .filter(
            __import__("app.models.membership", fromlist=["Membership"]).Membership.team_id == team_id,
            __import__("app.models.membership", fromlist=["Membership"]).Membership.removed_at.is_(None),
        )
        .all()
    ]
    for uid in member_ids:
        warn = schedule_service.overload_warning(db, team_id=team_id, user_id=uid, week_start=week_start)
        if warn:
            rows.append(warn)
    return {"items": rows}
