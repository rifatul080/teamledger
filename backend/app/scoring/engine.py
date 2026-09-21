"""Pure scoring engine. NO database, network, clock or random.

The same inputs always produce the same output bytes. Decimal arithmetic only.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, getcontext

# Use plenty of precision; final rounding happens at the boundary.
getcontext().prec = 28


ZERO = Decimal("0")
ONE = Decimal("1")
FIVE = Decimal("5")
HUNDRED = Decimal("100")


def _to_decimal(x: int | float | str | Decimal) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


@dataclass(frozen=True)
class CategoryConfig:
    """Per-project multiplier for a CRediT category. Default 1.0."""

    code: str
    multiplier: Decimal = ONE


@dataclass(frozen=True)
class TimelinessConfig:
    """Project-scoped timeliness bands, in whole days.

    Submitted days late are calculated from task.due_date to the first
    submission for review (NOT to acceptance). Bands and multipliers are
    configurable. Defaults match ``docs/architecture.md``.
    """

    on_time_band_days: int = 0          # <= due date
    mild_band_days: int = 2             # <= 2 days late -> 0.9
    medium_band_days: int = 7           # <= 7 days late -> 0.75
    late_mild: Decimal = Decimal("0.9")
    late_medium: Decimal = Decimal("0.75")
    late_severe: Decimal = Decimal("0.5")
    formula_version: str = "1.0.0"


@dataclass(frozen=True)
class TaskInput:
    """The minimum data the engine needs to score a task."""

    task_id: str
    assignee_user_id: str
    category_code: str
    weight: int                       # 1..10
    quality: int                      # 1..5  (0 if not yet reviewed)
    due_date: date
    first_submitted_at: datetime | None  # naive or aware; aware coerced to UTC


@dataclass(frozen=True)
class AdjustmentInput:
    user_id: str
    delta: Decimal
    reason: str
    author_user_id: str
    created_at: datetime


@dataclass(frozen=True)
class ParticipantInput:
    user_id: str
    display_name: str


@dataclass(frozen=True)
class PinnedPosition:
    """A position the leader has locked to a specific user."""

    position: int  # 1-based
    user_id: str
    note: str | None = None


@dataclass(frozen=True)
class FinalPosition:
    """A position in the leader's final order (and a note if differs from suggestion)."""

    position: int  # 1-based
    user_id: str
    note: str | None = None


@dataclass(frozen=True)
class ProjectInputs:
    project_id: str
    settings: TimelinessConfig
    categories: Sequence[CategoryConfig]
    participants: Sequence[ParticipantInput]
    tasks: Sequence[TaskInput]
    adjustments: Sequence[AdjustmentInput] = field(default_factory=list)
    pinned: Sequence[PinnedPosition] = field(default_factory=list)
    final_order: Sequence[FinalPosition] | None = None
    final_notes: dict[int, str] = field(default_factory=dict)
    formula_version: str = "1.0.0"


@dataclass(frozen=True)
class TaskBreakdown:
    task_id: str
    assignee_user_id: str
    category_code: str
    weight: int
    quality: int
    days_late: int | None
    timeliness: Decimal
    category_multiplier: Decimal
    points: Decimal  # 0 if not yet reviewed


@dataclass(frozen=True)
class ParticipantBreakdown:
    user_id: str
    display_name: str
    total_points: Decimal
    share_pct: Decimal
    by_category: dict[str, Decimal]
    tasks: list[TaskBreakdown]
    adjustments: list[AdjustmentInput]


@dataclass(frozen=True)
class OrderPosition:
    position: int
    user_id: str
    suggested: bool
    note: str | None


@dataclass(frozen=True)
class ScoreResult:
    project_id: str
    formula_version: str
    participants: list[ParticipantBreakdown]
    total_points: Decimal
    suggested_order: list[OrderPosition]
    final_order: list[OrderPosition] | None
    task_breakdowns: list[TaskBreakdown]


# ---------------------------------------------------------------------------
# Helpers


def _days_late(due: date, submitted_at: datetime | None) -> int | None:
    if submitted_at is None:
        return None
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)
    submitted_date = submitted_at.astimezone(UTC).date()
    delta = (submitted_date - due).days
    return delta if delta > 0 else 0


def _timeliness(days_late: int | None, cfg: TimelinessConfig) -> Decimal:
    if days_late is None:
        return ZERO
    if days_late <= cfg.on_time_band_days:
        return ONE
    if days_late <= cfg.mild_band_days:
        return _to_decimal(cfg.late_mild)
    if days_late <= cfg.medium_band_days:
        return _to_decimal(cfg.late_medium)
    return _to_decimal(cfg.late_severe)


def _round(x: Decimal) -> Decimal:
    """Round to 6 decimal places, half-up."""
    return x.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Pure functions


def calculate_task_points(task: TaskInput, cfg: TimelinessConfig, mult: Decimal) -> tuple[TaskBreakdown, Decimal]:
    """Returns the task breakdown plus raw (un-rounded) points.

    Raw points are returned so callers can sum at full precision; rounded
    points are stored on the breakdown for display.
    """
    days = _days_late(task.due_date, task.first_submitted_at)
    timeliness = _timeliness(days, cfg)
    weight = _to_decimal(task.weight)
    quality = _to_decimal(task.quality)
    multiplier = _to_decimal(mult)
    raw = ZERO if task.quality == 0 else weight * (quality / FIVE) * timeliness * multiplier
    rounded = _round(raw)
    breakdown = TaskBreakdown(
        task_id=task.task_id,
        assignee_user_id=task.assignee_user_id,
        category_code=task.category_code,
        weight=task.weight,
        quality=task.quality,
        days_late=days,
        timeliness=timeliness,
        category_multiplier=multiplier,
        points=rounded,
    )
    return breakdown, raw


def build_category_map(cats: Iterable[CategoryConfig]) -> dict[str, Decimal]:
    out = {c.code: _to_decimal(c.multiplier) for c in cats}
    return out


def compute_project_score(inputs: ProjectInputs) -> ScoreResult:
    cat_map = build_category_map(inputs.categories)
    breakdown_by_task: list[TaskBreakdown] = []
    raw_totals: dict[str, Decimal] = {p.user_id: ZERO for p in inputs.participants}
    by_category: dict[str, dict[str, Decimal]] = {
        p.user_id: {} for p in inputs.participants
    }
    tasks_per_user: dict[str, list[TaskBreakdown]] = {p.user_id: [] for p in inputs.participants}

    for task in inputs.tasks:
        mult = cat_map.get(task.category_code, ONE)
        breakdown, raw = calculate_task_points(task, inputs.settings, mult)
        breakdown_by_task.append(breakdown)
        uid = task.assignee_user_id
        if uid in raw_totals:
            raw_totals[uid] += raw
            tasks_per_user.setdefault(uid, []).append(breakdown)
            by_category[uid][task.category_code] = (
                by_category[uid].get(task.category_code, ZERO) + raw
            )

    # Apply adjustments (which are independent of any task and have a reason).
    adjustments_by_user: dict[str, list[AdjustmentInput]] = {p.user_id: [] for p in inputs.participants}
    for adj in inputs.adjustments:
        adjustments_by_user.setdefault(adj.user_id, []).append(adj)
        if adj.user_id in raw_totals:
            raw_totals[adj.user_id] += _to_decimal(adj.delta)

    # Round at the boundary.
    totals_rounded: dict[str, Decimal] = {uid: _round(v) for uid, v in raw_totals.items()}
    total = sum(totals_rounded.values(), start=ZERO)

    # Build participant breakdown list.
    breakdowns: list[ParticipantBreakdown] = []
    for p in inputs.participants:
        pct = ZERO
        if total > ZERO:
            pct = _round((totals_rounded[p.user_id] / total) * HUNDRED)
        rounded_by_cat = {k: _round(v) for k, v in by_category[p.user_id].items()}
        breakdowns.append(
            ParticipantBreakdown(
                user_id=p.user_id,
                display_name=p.display_name,
                total_points=totals_rounded[p.user_id],
                share_pct=pct,
                by_category=rounded_by_cat,
                tasks=tasks_per_user.get(p.user_id, []),
                adjustments=adjustments_by_user.get(p.user_id, []),
            )
        )

    suggested = suggest_order(breakdowns, inputs.pinned)

    final_order = None
    if inputs.final_order is not None:
        final_order = build_final_order(suggested, inputs.final_order, inputs.final_notes)

    return ScoreResult(
        project_id=inputs.project_id,
        formula_version=inputs.formula_version,
        participants=breakdowns,
        total_points=_round(total),
        suggested_order=suggested,
        final_order=final_order,
        task_breakdowns=breakdown_by_task,
    )


# ---------------------------------------------------------------------------
# Tie-break rules and ordering


def tie_break_key(p: ParticipantBreakdown) -> tuple[int, str, str]:
    """Stable, total ordering across participants.

    - points desc (higher first)
    - display_name asc, case-insensitive Unicode codepoint
    - user_id asc (ULID is monotonic, this is a final stable tiebreaker)
    """

    return (
        -int((p.total_points * Decimal("1000000")).to_integral_value()),
        p.display_name.casefold(),
        p.user_id,
    )


def sort_key(p: ParticipantBreakdown) -> tuple[int, str, str]:
    return tie_break_key(p)


def suggest_order(
    participants: Sequence[ParticipantBreakdown],
    pinned: Sequence[PinnedPosition] = (),
) -> list[OrderPosition]:
    """Ranking by points desc with the documented tie-break.

    Pinned positions are filled first; remaining slots are filled by the
    ranking, skipping pinned users. Pinned positions that collide with each
    other raise ``ValueError``.
    """
    pin_by_pos: dict[int, str] = {}
    for pp in pinned:
        if pp.position in pin_by_pos and pin_by_pos[pp.position] != pp.user_id:
            raise ValueError(f"pinned position {pp.position} collides")
        pin_by_pos[pp.position] = pp.user_id

    pinned_users = set(pin_by_pos.values())
    remaining = sorted(
        [p for p in participants if p.user_id not in pinned_users],
        key=sort_key,
    )

    n = len(participants)
    out: list[OrderPosition] = []
    cursor = 0
    for pos in range(1, n + 1):
        if pos in pin_by_pos:
            uid = pin_by_pos[pos]
            note = next((p.note for p in pinned if p.position == pos), None)
            out.append(OrderPosition(position=pos, user_id=uid, suggested=False, note=note))
        else:
            if cursor >= len(remaining):
                continue
            p = remaining[cursor]
            cursor += 1
            out.append(OrderPosition(position=pos, user_id=p.user_id, suggested=True, note=None))

    # If the leader specified fewer final positions than participants, we
    # simply fill what we have; missing tails remain "unplaced".
    return out


def build_final_order(
    suggested: Sequence[OrderPosition],
    final_positions: Sequence[FinalPosition],
    notes: dict[int, str],
) -> list[OrderPosition]:
    """Annotate the leader's final positions with ``suggested=False`` if they
    differ from the suggestion. ``notes[pos]`` may be empty string.
    """
    suggestion_for = {o.user_id: o for o in suggested}
    out: list[OrderPosition] = []
    for fp in final_positions:
        s = suggestion_for.get(fp.user_id)
        differs = (s is None) or (s.position != fp.position)
        note = fp.note if fp.note is not None else notes.get(fp.position)
        out.append(OrderPosition(position=fp.position, user_id=fp.user_id, suggested=not differs, note=note))
    return out
