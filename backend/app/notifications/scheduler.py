"""Idempotent scheduler: 3-day, 1-day, overdue notifications."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..core.clock import Clock
from ..core.ids import new_id
from ..models.notification import NotificationKey
from ..models.task import Task
from . import mail as notif

log = logging.getLogger("teamledger.scheduler")


def _already_fired(db: Session, *, kind: str, task_id: str, recipient_id: str, bucket: str) -> bool:
    existing = (
        db.query(NotificationKey)
        .filter(
            NotificationKey.kind == kind,
            NotificationKey.task_id == task_id,
            NotificationKey.recipient_id == recipient_id,
            NotificationKey.bucket == bucket,
        )
        .one_or_none()
    )
    return existing is not None


def _mark_fired(db: Session, *, kind: str, task_id: str, recipient_id: str, bucket: str) -> None:
    db.add(
        NotificationKey(
            id=new_id(),
            kind=kind,
            task_id=task_id,
            recipient_id=recipient_id,
            bucket=bucket,
        )
    )
    try:
        db.flush()
    except Exception:
        db.rollback()
        raise


def run_deadline_reminders(db: Session, clock: Clock) -> dict[str, int]:
    """Run all deadline-related notifications. Idempotent.

    Returns counters: ``{"3d": N, "1d": M, "overdue": K}``.
    """
    today = clock.today()
    counters = {"3d": 0, "1d": 0, "overdue": 0}
    rows = (
        db.query(Task)
        .filter(Task.status.notin_(["done"]))
        .all()
    )
    for t in rows:
        delta = (t.due_date - today).days
        bucket3 = f"due-{t.due_date.isoformat()}-3d"
        bucket1 = f"due-{t.due_date.isoformat()}-1d"
        bucket_over = f"overdue-{t.due_date.isoformat()}"
        if delta == 3:
            if _already_fired(
                db, kind="deadline_3d", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket3
            ):
                continue
            _mark_fired(
                db, kind="deadline_3d", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket3
            )
            notif.emit(
                db,
                [
                    notif.NotifRequest(
                        user_id=t.assignee_user_id,
                        type="deadline_3d",
                        title="Task due in 3 days",
                        body=f"Task {t.title!r} is due on {t.due_date.isoformat()}.",
                        task_id=t.id,
                    )
                ],
            )
            counters["3d"] += 1
        if delta == 1:
            if _already_fired(
                db, kind="deadline_1d", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket1
            ):
                continue
            _mark_fired(
                db, kind="deadline_1d", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket1
            )
            notif.emit(
                db,
                [
                    notif.NotifRequest(
                        user_id=t.assignee_user_id,
                        type="deadline_1d",
                        title="Task due tomorrow",
                        body=f"Task {t.title!r} is due on {t.due_date.isoformat()}.",
                        task_id=t.id,
                    )
                ],
            )
            counters["1d"] += 1
        if delta < 0:
            if _already_fired(
                db, kind="overdue", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket_over
            ):
                continue
            _mark_fired(
                db, kind="overdue", task_id=t.id, recipient_id=t.assignee_user_id, bucket=bucket_over
            )
            notif.emit(
                db,
                [
                    notif.NotifRequest(
                        user_id=t.assignee_user_id,
                        type="overdue",
                        title="Task overdue",
                        body=f"Task {t.title!r} was due on {t.due_date.isoformat()}.",
                        task_id=t.id,
                    )
                ],
            )
            counters["overdue"] += 1
    db.commit()
    return counters


def start_scheduler(clock: Clock) -> None:
    """Start APScheduler in the FastAPI process. Idempotent — multiple calls
    replace the existing scheduler."""
    from apscheduler.schedulers.background import BackgroundScheduler

    from ..db.session import session_scope

    sched = BackgroundScheduler(daemon=True)

    def _tick() -> None:
        try:
            with next(session_scope()) as db:
                run_deadline_reminders(db, clock)
        except Exception:
            log.exception("reminder tick failed")

    sched.add_job(_tick, "interval", minutes=10, id="reminders", replace_existing=True)
    sched.start()
    log.info("scheduler started")
