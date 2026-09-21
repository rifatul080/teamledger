"""Schedule service: weekly availability plans + overload checks."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..core.errors import validation
from ..core.ids import new_id
from ..models.goal import Goal
from ..models.milestone import Milestone
from ..models.schedule import ScheduleSlot, WeeklyPlan
from ..models.task import Task
from ..models.team import Team


def iso_week_start(d: date) -> date:
    """Return the Monday of the week containing ``d``."""
    return d - timedelta(days=d.weekday())


def set_plan(
    db: Session, *, team: Team, user_id: str, weekly_cap_hours: int, slots: list[dict]
) -> WeeklyPlan:
    plan = (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.team_id == team.id, WeeklyPlan.user_id == user_id)
        .one_or_none()
    )
    if plan is None:
        plan = WeeklyPlan(id=new_id(), team_id=team.id, user_id=user_id, weekly_cap_hours=weekly_cap_hours)
        db.add(plan)
        db.flush()
    else:
        plan.weekly_cap_hours = weekly_cap_hours
        # replace slots
        db.query(ScheduleSlot).filter(ScheduleSlot.weekly_plan_id == plan.id).delete()
    for s in slots:
        if s["start_minute"] >= s["end_minute"]:
            raise validation("Slot end must be after start.")
        db.add(
            ScheduleSlot(
                id=new_id(),
                weekly_plan_id=plan.id,
                weekday=s["weekday"],
                start_minute=s["start_minute"],
                end_minute=s["end_minute"],
                note=s.get("note"),
            )
        )
    db.flush()
    return plan


def get_plan(db: Session, *, team_id: str, user_id: str) -> WeeklyPlan | None:
    return (
        db.query(WeeklyPlan)
        .filter(WeeklyPlan.team_id == team_id, WeeklyPlan.user_id == user_id)
        .one_or_none()
    )


def hours_in_week(db: Session, *, team_id: str, user_id: str, week_start: date) -> int:
    """Compute the total estimated hours assigned to the user whose due_date
    falls inside the calendar week ``[week_start, week_start+7)``.
    """
    week_end = week_start + timedelta(days=7)
    rows = (
        db.query(Task)
        .join(Milestone, Milestone.id == Task.milestone_id)
        .join(Goal, Goal.id == Milestone.goal_id)
        .filter(
            Task.assignee_user_id == user_id,
            Task.due_date >= week_start,
            Task.due_date < week_end,
            Task.status != "done",
        )
        .all()
    )
    return sum(t.est_hours for t in rows)


def overload_warning(db: Session, *, team_id: str, user_id: str, week_start: date) -> dict | None:
    plan = get_plan(db, team_id=team_id, user_id=user_id)
    if plan is None:
        return None
    hours = hours_in_week(db, team_id=team_id, user_id=user_id, week_start=week_start)
    if hours > plan.weekly_cap_hours:
        return {
            "user_id": user_id,
            "week_start": week_start.isoformat(),
            "assigned_hours": hours,
            "cap_hours": plan.weekly_cap_hours,
        }
    return None


def calendar(
    db: Session, *, team_id: str, range_start: date, range_end: date, user_id: str | None = None
) -> dict:
    """Return a flat list of events (tasks + milestones + deadlines) for the team/period."""
    tasks_q = (
        db.query(Task)
        .join(Milestone, Milestone.id == Task.milestone_id)
        .join(Goal, Goal.id == Milestone.goal_id)
        .filter(Goal.project_id.in_(_team_project_ids(db, team_id)))
    )
    if user_id:
        tasks_q = tasks_q.filter(Task.assignee_user_id == user_id)
    tasks = [t for t in tasks_q.all() if t.start_date <= range_end and t.due_date >= range_start]
    events = []
    for t in tasks:
        events.append(
            {
                "kind": "task",
                "id": t.id,
                "title": t.title,
                "assignee_user_id": t.assignee_user_id,
                "start_date": t.start_date.isoformat(),
                "due_date": t.due_date.isoformat(),
                "status": t.status,
            }
        )
    milestones = (
        db.query(Milestone)
        .join(Goal, Goal.id == Milestone.goal_id)
        .filter(
            Goal.project_id.in_(_team_project_ids(db, team_id)),
            Milestone.due_date >= range_start,
            Milestone.due_date <= range_end,
        )
        .all()
    )
    for m in milestones:
        events.append(
            {
                "kind": "milestone",
                "id": m.id,
                "title": m.title,
                "due_date": m.due_date.isoformat(),
            }
        )
    events.sort(key=lambda e: e.get("due_date") or e.get("start_date"))
    return {"items": events}


def timeline(
    db: Session, *, team_id: str, range_start: date, range_end: date, user_id: str | None = None
) -> dict:
    """Same content as calendar but grouped by date for a Gantt-style view."""
    flat = calendar(db, team_id=team_id, range_start=range_start, range_end=range_end, user_id=user_id)
    grouped: dict[str, list[dict]] = {}
    for ev in flat["items"]:
        key = ev.get("due_date") or ev.get("start_date") or ""
        grouped.setdefault(key, []).append(ev)
    return {"days": [{"date": d, "events": grouped[d]} for d in sorted(grouped)]}


def _team_project_ids(db: Session, team_id: str) -> list[str]:
    from ..models.project import Project

    rows = db.query(Project.id).filter(Project.team_id == team_id).all()
    return [r[0] for r in rows]
