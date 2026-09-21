"""Task service: goals, milestones, tasks, submissions, reviews."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..core.errors import not_found, validation
from ..core.ids import new_id
from ..models.goal import Goal
from ..models.milestone import Milestone
from ..models.task import Task
from ..models.task_review import TaskReview
from ..models.task_submission import TaskSubmission
from ..models.user import User
from ..scoring.engine import (
    ProjectInputs,
    ScoreResult,
    TimelinessConfig,
    compute_project_score,
)
from . import credit as credit_service
from . import project_service

# ---------------------------------------------------------------------------
# Goals / milestones

def create_goal(db: Session, *, project_id: str, title: str, description: str | None, target_date) -> Goal:
    g = Goal(id=new_id(), project_id=project_id, title=title, description=description, target_date=target_date)
    db.add(g)
    db.flush()
    return g


def update_goal(db: Session, goal: Goal, **fields) -> Goal:
    for k, v in fields.items():
        if v is not None and hasattr(goal, k):
            setattr(goal, k, v)
    db.flush()
    return goal


def goal_progress(db: Session, goal: Goal) -> float:
    """0..100 progress percentage."""
    ms_ids = [m.id for m in db.query(Milestone).filter(Milestone.goal_id == goal.id).all()]
    if not ms_ids:
        return 0.0
    rows = (
        db.query(Task)
        .filter(Task.milestone_id.in_(ms_ids))
        .all()
    )
    if not rows:
        return 0.0
    done = sum(1 for t in rows if t.status == "done")
    return round(done / len(rows), 4) * 100.0


def milestone_progress(db: Session, milestone: Milestone) -> float:
    rows = db.query(Task).filter(Task.milestone_id == milestone.id).all()
    if not rows:
        return 0.0
    done = sum(1 for t in rows if t.status == "done")
    return round(done / len(rows), 4) * 100.0


def create_milestone(db: Session, *, goal_id: str, title: str, due_date) -> Milestone:
    m = Milestone(id=new_id(), goal_id=goal_id, title=title, due_date=due_date)
    db.add(m)
    db.flush()
    return m


def update_milestone(db: Session, milestone: Milestone, **fields) -> Milestone:
    for k, v in fields.items():
        if v is not None and hasattr(milestone, k):
            setattr(milestone, k, v)
    db.flush()
    return milestone


# ---------------------------------------------------------------------------
# Tasks

def create_task(
    db: Session,
    *,
    milestone_id: str,
    assignee: User,
    actor: User,
    title: str,
    description: str | None,
    category_code: str,
    weight: int,
    est_hours: int,
    start_date,
    due_date,
    proposed: bool = False,
    proposer: User | None = None,
    split_from_task_id: str | None = None,
) -> Task:
    if not credit_service.is_valid_category(category_code):
        raise validation("Unknown CRediT category.", code="credit.invalid")
    if not (1 <= weight <= 10):
        raise validation("Weight must be between 1 and 10.", code="task.weight_invalid")
    t = Task(
        id=new_id(),
        milestone_id=milestone_id,
        assignee_user_id=assignee.id,
        category_code=category_code,
        title=title,
        description=description,
        weight=weight,
        est_hours=est_hours,
        start_date=start_date,
        due_date=due_date,
        status=("proposed" if proposed else "todo"),
        proposed=proposed,
        proposer_user_id=(proposer.id if proposer else None),
        split_from_task_id=split_from_task_id,
    )
    db.add(t)
    db.flush()
    return t


def update_task(db: Session, task: Task, *, actor: User, **fields) -> Task:
    if fields.get("category_code"):
        if not credit_service.is_valid_category(fields["category_code"]):
            raise validation("Unknown CRediT category.", code="credit.invalid")
        task.category_code = fields["category_code"]
    if "weight" in fields and fields["weight"] is not None:
        if not (1 <= fields["weight"] <= 10):
            raise validation("Weight must be between 1 and 10.", code="task.weight_invalid")
        task.weight = fields["weight"]
        # already-accepted tasks cannot change weight.
        if task.status == "done":
            raise validation("Cannot change weight of an accepted task.", code="task.weight_locked")
    # Other field updates: assignee must be a participant.
    if fields.get("assignee_user_id"):
        new_assignee = fields["assignee_user_id"]
        # Locate the project from the milestone.
        ms = db.get(Milestone, task.milestone_id)
        if ms is None:
            raise not_found()
        goal = db.get(Goal, ms.goal_id)
        if goal is None:
            raise not_found()
        if not project_service.is_participant(db, goal.project_id, new_assignee):
            raise validation(
                "Assignee must be a project participant.",
                code="task.assignee_not_participant",
            )
        task.assignee_user_id = new_assignee
    for k in ("title", "description", "est_hours", "start_date", "due_date", "status"):
        if fields.get(k) is not None:
            setattr(task, k, fields[k])
    db.flush()
    return task


def propose_task(db: Session, *, milestone_id: str, proposer: User, **fields) -> Task:
    """A member proposes a task; leader later approves."""
    t = create_task(
        db,
        milestone_id=milestone_id,
        assignee=proposer,  # placeholder until leader approves
        actor=proposer,
        title=fields["title"],
        description=fields.get("description"),
        category_code=fields["category_code"],
        weight=fields["weight"],
        est_hours=fields["est_hours"],
        start_date=fields["start_date"],
        due_date=fields["due_date"],
        proposed=True,
        proposer=proposer,
    )
    return t


def split_task(
    db: Session,
    *,
    task: Task,
    actor: User,
    new_assignee: User,
    weight: int,
    est_hours: int,
    category_code: str,
    title: str | None,
) -> Task:
    """Split a task by creating a sibling with a different assignee."""
    from . import credit as credit_service

    if not credit_service.is_valid_category(category_code):
        raise validation("Unknown CRediT category.", code="credit.invalid")
    if not (1 <= weight <= 10):
        raise validation("Weight must be between 1 and 10.", code="task.weight_invalid")
    if new_assignee.id == task.assignee_user_id:
        raise validation("Split requires a different assignee.", code="task.split_same_assignee")
    ms = db.get(Milestone, task.milestone_id)
    if ms is None:
        raise not_found()
    goal = db.get(Goal, ms.goal_id)
    if not project_service.is_participant(db, goal.project_id, new_assignee.id):
        raise validation("New assignee must be a project participant.", code="task.assignee_not_participant")
    new_title = title or f"{task.title} (split)"
    new_task = create_task(
        db,
        milestone_id=task.milestone_id,
        assignee=new_assignee,
        actor=actor,
        title=new_title,
        description=task.description,
        category_code=category_code,
        weight=weight,
        est_hours=est_hours,
        start_date=task.start_date,
        due_date=task.due_date,
        split_from_task_id=task.id,
    )
    return new_task


def approve_proposed_task(db: Session, *, task: Task, assignee: User, actor: User) -> Task:
    """Leader approves a proposed task — sets assignee, marks not proposed."""
    if not task.proposed:
        raise validation("Task is not a proposal.", code="task.not_proposed")
    ms = db.get(Milestone, task.milestone_id)
    if ms is None:
        raise not_found()
    goal = db.get(Goal, ms.goal_id)
    if goal is None or not project_service.is_participant(db, goal.project_id, assignee.id):
        raise validation("Assignee must be a project participant.", code="task.assignee_not_participant")
    task.assignee_user_id = assignee.id
    task.proposed = False
    task.status = "todo"
    db.flush()
    return task


def submit_for_review(db: Session, *, task: Task, actor: User, note: str | None) -> Task:
    if task.proposed:
        raise validation("Proposals cannot be submitted.", code="task.submit_proposed")
    if task.status not in ("todo", "in_progress", "needs_rework"):
        raise validation(
            f"Cannot submit task in status {task.status!r}.",
            code="task.submit_invalid_state",
        )
    now = datetime.now(tz=UTC)
    seq = (
        db.query(TaskSubmission)
        .filter(TaskSubmission.task_id == task.id)
        .count()
    ) + 1
    db.add(
        TaskSubmission(
            id=new_id(),
            task_id=task.id,
            seq=seq,
            submitted_by_user_id=actor.id,
            submitted_at=now,
        )
    )
    if task.first_submitted_at is None:
        task.first_submitted_at = now
    task.status = "in_review"
    db.flush()
    return task


def review_task(
    db: Session,
    *,
    task: Task,
    reviewer: User,
    decision: str,
    quality: int,
    note: str | None,
) -> tuple[Task, TaskReview]:
    if not (1 <= quality <= 5):
        raise validation("Quality must be 1..5.", code="review.quality_range")
    if task.status != "in_review":
        raise validation(
            f"Task must be in_review to be reviewed (got {task.status!r}).",
            code="review.wrong_state",
        )
    if decision not in ("accept", "reject"):
        raise validation("Decision must be 'accept' or 'reject'.", code="review.decision")
    if reviewer.id == task.assignee_user_id:
        raise validation("You cannot review your own task.", code="review.self")
    now = datetime.now(tz=UTC)
    rev = TaskReview(
        id=new_id(),
        task_id=task.id,
        reviewer_user_id=reviewer.id,
        quality=quality,
        decision=decision,
        note=note,
        decided_at=now,
    )
    db.add(rev)
    if decision == "reject":
        task.status = "needs_rework"
    else:
        task.status = "done"
        task.accepted_at = now
        # Compute points immediately using the current timeliness settings
        # and category multipliers; we still keep ``points_awarded`` so the
        # dashboard can re-render without re-running the engine.
        ms = db.get(Milestone, task.milestone_id)
        goal = db.get(Goal, ms.goal_id)
        ts = project_service.get_timeliness(db, goal.project_id)
        cfg = TimelinessConfig(
            on_time_band_days=ts.on_time_band_days,
            mild_band_days=ts.mild_band_days,
            medium_band_days=ts.medium_band_days,
            late_mild=Decimal(str(ts.late_mild)),
            late_medium=Decimal(str(ts.late_medium)),
            late_severe=Decimal(str(ts.late_severe)),
        )
        cats = project_service.get_category_multipliers(db, goal.project_id)
        from ..scoring.engine import TaskInput

        multiplier = cats.get(task.category_code, Decimal("1.0"))
        breakdown, _ = __import__("app.scoring.engine", fromlist=["calculate_task_points"]).calculate_task_points(
            TaskInput(
                task_id=task.id,
                assignee_user_id=task.assignee_user_id,
                category_code=task.category_code,
                weight=task.weight,
                quality=quality,
                due_date=task.due_date,
                first_submitted_at=task.first_submitted_at,
            ),
            cfg,
            multiplier,
        )
        task.points_awarded = breakdown.points
    db.flush()
    return task, rev


# ---------------------------------------------------------------------------
# Score computation entry point

def build_score_inputs(db: Session, project_id: str) -> ProjectInputs:
    from ..models.participant import ProjectParticipant
    from ..models.score_adjustment import ScoreAdjustment
    from ..models.user import User
    from ..scoring.engine import (
        AdjustmentInput,
        CategoryConfig,
        ParticipantInput,
        TaskInput,
    )

    ts = project_service.get_timeliness(db, project_id)
    cfg = TimelinessConfig(
        on_time_band_days=ts.on_time_band_days,
        mild_band_days=ts.mild_band_days,
        medium_band_days=ts.medium_band_days,
        late_mild=Decimal(str(ts.late_mild)),
        late_medium=Decimal(str(ts.late_medium)),
        late_severe=Decimal(str(ts.late_severe)),
    )
    cats = [
        CategoryConfig(code=code, multiplier=Decimal(str(mul)))
        for code, mul in project_service.get_category_multipliers(db, project_id).items()
    ]

    participant_user_ids = {
        p.user_id
        for p in db.query(ProjectParticipant).filter(ProjectParticipant.project_id == project_id).all()
    }
    user_rows = db.query(User).filter(User.id.in_(participant_user_ids)).all()
    participants = [ParticipantInput(user_id=u.id, display_name=u.display_name) for u in user_rows]

    task_inputs: list[TaskInput] = []
    for t in (
        db.query(Task)
        .join(Milestone, Milestone.id == Task.milestone_id)
        .join(Goal, Goal.id == Milestone.goal_id)
        .filter(Goal.project_id == project_id)
        .all()
    ):
        if t.points_awarded is None:
            quality = 0
        else:
            # find accept-quality from reviews (the last accept wins)
            accept_rev = (
                db.query(TaskReview)
                .filter(TaskReview.task_id == t.id, TaskReview.decision == "accept")
                .order_by(TaskReview.decided_at.desc())
                .first()
            )
            quality = accept_rev.quality if accept_rev else 0
        task_inputs.append(
            TaskInput(
                task_id=t.id,
                assignee_user_id=t.assignee_user_id,
                category_code=t.category_code,
                weight=t.weight,
                quality=quality,
                due_date=t.due_date,
                first_submitted_at=t.first_submitted_at,
            )
        )

    adj_inputs: list[AdjustmentInput] = []
    for a in db.query(ScoreAdjustment).filter(ScoreAdjustment.project_id == project_id).all():
        adj_inputs.append(
            AdjustmentInput(
                user_id=a.user_id,
                delta=Decimal(str(a.delta)),
                reason=a.reason,
                author_user_id=a.author_user_id,
                created_at=a.created_at,
            )
        )

    return ProjectInputs(
        project_id=project_id,
        settings=cfg,
        categories=cats,
        participants=participants,
        tasks=task_inputs,
        adjustments=adj_inputs,
    )


def compute_score(db: Session, project_id: str) -> ScoreResult:
    inputs = build_score_inputs(db, project_id)
    return compute_project_score(inputs)
