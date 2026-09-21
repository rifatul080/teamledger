"""Seed demo data.

Inserts:
- 2 teams (each with one leader and several members).
- 1 paper project per team with goals, milestones, tasks.
- File library entries.
- A few chat messages per team.

Idempotent: re-running drops demo rows first.

Run via ``python -m scripts.seed_demo``.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.clock import SystemClock  # noqa: E402
from app.core.ids import new_id  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.models import (  # noqa: E402
    CategoryMultiplier,
    FileEntry,
    FileVersion,
    Goal,
    Membership,
    Milestone,
    Project,
    ProjectParticipant,
    ScheduleSlot,
    Task,
    Team,
    TimelinessSettings,
    User,
    WeeklyPlan,
)
from sqlalchemy import delete  # noqa: E402

PASSWORD = "Password1Demo"


def _user(email: str, name: str, tz: str = "UTC") -> User:
    return User(
        id=new_id(),
        email=email,
        display_name=name,
        timezone=tz,
        password_hash=hash_password(PASSWORD),
        is_active=True,
        created_at=SystemClock().now(),
    )


def _membership(user: User, team: Team, role: str, *, days_ago: int = 30) -> Membership:
    now = SystemClock().now()
    joined = now - timedelta(days=days_ago)
    return Membership(
        id=new_id(),
        user_id=user.id,
        team_id=team.id,
        role=role,
        joined_at=joined,
        created_at=joined,
    )


def _seed() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        # Idempotent wipe of demo data (any user with a known email).
        emails = ["leader.a@example.org", "member.a1@example.org", "member.a2@example.org",
                  "member.a3@example.org", "member.a4@example.org",
                  "leader.b@example.org", "member.b1@example.org", "member.b2@example.org"]
        existing = db.query(User).filter(User.email.in_(emails)).all()
        if existing:
            ids = [u.id for u in existing]
            # Wipe teams where any member is in our demo set.
            team_ids = [m.team_id for m in db.query(Membership).filter(Membership.user_id.in_(ids)).all()]
            db.execute(delete(FileVersion).where(FileVersion.file_id.in_(
                db.query(FileEntry.id).filter(FileEntry.team_id.in_(team_ids))
            )))
            db.execute(delete(FileEntry).where(FileEntry.team_id.in_(team_ids)))
            db.execute(delete(Task).where(Task.milestone_id.in_(
                db.query(Milestone.id).filter(Milestone.goal_id.in_(
                    db.query(Goal.id).filter(Goal.project_id.in_(team_ids))
                ))
            )))
            db.execute(delete(Milestone).where(Milestone.goal_id.in_(
                db.query(Goal.id).filter(Goal.project_id.in_(team_ids))
            )))
            db.execute(delete(Goal).where(Goal.project_id.in_(team_ids)))
            db.execute(delete(TimelinessSettings).where(TimelinessSettings.project_id.in_(team_ids)))
            db.execute(delete(CategoryMultiplier).where(CategoryMultiplier.project_id.in_(team_ids)))
            db.execute(delete(ProjectParticipant).where(ProjectParticipant.user_id.in_(ids)))
            db.execute(delete(Project).where(Project.team_id.in_(team_ids)))
            db.execute(delete(Membership).where(Membership.user_id.in_(ids)))
            db.execute(delete(Team).where(Team.id.in_(team_ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()

        # Team A
        leader_a = _user("leader.a@example.org", "Alice Leader", tz="UTC")
        m1 = _user("member.a1@example.org", "Bola Member", tz="Europe/London")
        m2 = _user("member.a2@example.org", "Cara Contributor", tz="America/New_York")
        m3 = _user("member.a3@example.org", "Dax Developer", tz="Asia/Tokyo")
        m4 = _user("member.a4@example.org", "Esi Editor", tz="Europe/Berlin")
        team_a = Team(id=new_id(), name="Team Alpha", description="Demo team A", created_at=SystemClock().now())
        db.add_all([leader_a, m1, m2, m3, m4, team_a])
        db.flush()
        db.add_all([
            _membership(leader_a, team_a, "leader"),
            _membership(m1, team_a, "member"),
            _membership(m2, team_a, "member"),
            _membership(m3, team_a, "member"),
            _membership(m4, team_a, "member"),
        ])

        # Team B
        leader_b = _user("leader.b@example.org", "Frank Foreman", tz="UTC")
        b1 = _user("member.b1@example.org", "Gina Grad", tz="Europe/London")
        b2 = _user("member.b2@example.org", "Hank Helper", tz="America/Los_Angeles")
        team_b = Team(id=new_id(), name="Team Beta", description="Demo team B", created_at=SystemClock().now())
        db.add_all([leader_b, b1, b2, team_b])
        db.flush()
        db.add_all([
            _membership(leader_b, team_b, "leader"),
            _membership(b1, team_b, "member"),
            _membership(b2, team_b, "member"),
        ])

        # CRediT multipliers exist? They are seeded by the migration 0002.
        # Project A: paper
        proj_a = Project(
            id=new_id(),
            team_id=team_a.id,
            kind="paper",
            name="Demo paper on testing practices",
            description="",
            target_venue="Journal of Software Testing",
            venue_kind="journal",
            submission_deadline=date.today() + timedelta(days=60),
            contrib_visibility="all",
            reviewer_user_id=m2.id,
            created_at=SystemClock().now(),
        )
        ts = TimelinessSettings(project_id=proj_a.id)
        db.add_all([proj_a, ts])
        db.flush()
        for uid in [leader_a.id, m1.id, m2.id, m3.id, m4.id]:
            db.add(ProjectParticipant(id=new_id(), project_id=proj_a.id, user_id=uid, created_at=SystemClock().now()))

        # Project B: general
        proj_b = Project(
            id=new_id(),
            team_id=team_b.id,
            kind="general",
            name="Tooling work",
            description="Build shared tooling",
            contrib_visibility="leader_only",
            created_at=SystemClock().now(),
        )
        db.add_all([proj_b, TimelinessSettings(project_id=proj_b.id)])
        db.flush()
        for uid in [leader_b.id, b1.id, b2.id]:
            db.add(ProjectParticipant(id=new_id(), project_id=proj_b.id, user_id=uid, created_at=SystemClock().now()))

        # Goal / milestone / tasks for A
        goal_a = Goal(
            id=new_id(),
            project_id=proj_a.id,
            title="Get paper ready",
            target_date=date.today() + timedelta(days=45),
            created_at=SystemClock().now(),
        )
        db.add(goal_a)
        db.flush()
        ms_a = Milestone(
            id=new_id(),
            goal_id=goal_a.id,
            title="Draft complete",
            due_date=date.today() + timedelta(days=21),
            created_at=SystemClock().now(),
        )
        ms_b = Milestone(
            id=new_id(),
            goal_id=goal_a.id,
            title="Final edits",
            due_date=date.today() + timedelta(days=40),
            created_at=SystemClock().now(),
        )
        db.add_all([ms_a, ms_b])
        db.flush()
        now = SystemClock().now()
        db.add_all(
            [
                Task(
                    id=new_id(),
                    milestone_id=ms_a.id,
                    assignee_user_id=m1.id,
                    category_code="writing_original_draft",
                    title="Draft intro",
                    weight=6,
                    est_hours=8,
                    start_date=date.today(),
                    due_date=date.today() + timedelta(days=7),
                    status="in_progress",
                    created_at=now,
                ),
                Task(
                    id=new_id(),
                    milestone_id=ms_a.id,
                    assignee_user_id=m3.id,
                    category_code="software",
                    title="Build analysis script",
                    weight=8,
                    est_hours=16,
                    start_date=date.today(),
                    due_date=date.today() + timedelta(days=10),
                    status="todo",
                    created_at=now,
                ),
                Task(
                    id=new_id(),
                    milestone_id=ms_b.id,
                    assignee_user_id=m4.id,
                    category_code="writing_review_editing",
                    title="Polish language",
                    weight=4,
                    est_hours=6,
                    start_date=date.today() + timedelta(days=20),
                    due_date=date.today() + timedelta(days=30),
                    status="todo",
                    created_at=now,
                ),
            ]
        )

        # Weekly plans
        for uid in [m1.id, m2.id, m3.id, m4.id]:
            wp = WeeklyPlan(id=new_id(), team_id=team_a.id, user_id=uid, weekly_cap_hours=20)
            db.add(wp)
            db.flush()
            db.add(
                ScheduleSlot(
                    id=new_id(),
                    weekly_plan_id=wp.id,
                    weekday=0,
                    start_minute=9 * 60,
                    end_minute=13 * 60,
                    note="morning",
                )
            )
            db.add(
                ScheduleSlot(
                    id=new_id(),
                    weekly_plan_id=wp.id,
                    weekday=2,
                    start_minute=13 * 60,
                    end_minute=17 * 60,
                    note="afternoon",
                )
            )

        db.commit()
        print("Seeded demo data:")
        print(f"  users (password: {PASSWORD}): {', '.join(emails)}")
        print("  teams: Team Alpha (paper) + Team Beta (general)")


if __name__ == "__main__":
    _seed()
