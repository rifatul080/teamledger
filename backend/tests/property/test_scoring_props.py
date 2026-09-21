"""Hypothesis property tests for scoring invariants."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import HealthCheck, given, settings, strategies as st

from app.scoring.engine import (
    AdjustmentInput,
    CategoryConfig,
    ParticipantInput,
    ProjectInputs,
    TaskInput,
    TimelinessConfig,
    compute_project_score,
)


# Strategies ----------------------------------------------------------------

dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
weights = st.integers(min_value=1, max_value=10)
qualities = st.integers(min_value=1, max_value=5)
cat_codes = st.sampled_from(
    [
        "conceptualization",
        "data_curation",
        "formal_analysis",
        "funding_acquisition",
        "investigation",
        "methodology",
        "project_administration",
        "resources",
        "software",
        "supervision",
        "validation",
        "visualization",
        "writing_original_draft",
        "writing_review_editing",
    ]
)
multipliers = st.decimals(min_value=Decimal("0"), max_value=Decimal("5"), places=3, allow_nan=False, allow_infinity=False)
user_ids = st.text(min_size=1, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))
display_names = st.text(min_size=1, max_size=12, alphabet=st.characters(whitelist_categories=("Lu", "Ll")))

participants = st.lists(
    st.tuples(user_ids, display_names).map(lambda x: ParticipantInput(user_id=x[0], display_name=x[1])),
    min_size=1,
    max_size=5,
    unique_by=lambda p: p.user_id,
)


def _ts() -> TimelinessConfig:
    return TimelinessConfig()


def _task_input(assignee: str, *, weight=5, quality=5, due=date(2025, 1, 10), submitted=None):
    return TaskInput(
        task_id=f"t-{assignee}-{weight}-{quality}-{due}",
        assignee_user_id=assignee,
        category_code="writing_original_draft",
        weight=weight,
        quality=quality,
        due_date=due,
        first_submitted_at=submitted,
    )


# Property tests -------------------------------------------------------------


@given(
    participants=participants,
    weight=weights,
    quality=qualities,
    mult=multipliers,
    days_late=st.integers(min_value=0, max_value=30),
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=30)
def test_render_is_deterministic(participants, weight, quality, mult, days_late) -> None:
    """Same inputs produce same outputs."""
    tasks = [
        _task_input(
            p.user_id, weight=weight, quality=quality,
            due=date(2025, 1, 10),
            submitted=datetime(2025, 1, 10, tzinfo=timezone.utc) + timedelta(days=days_late),
        )
        for p in participants
    ]
    inputs = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)],
        participants=participants,
        tasks=tasks,
    )
    a = compute_project_score(inputs)
    b = compute_project_score(inputs)
    assert a.total_points == b.total_points
    assert [p.total_points for p in a.participants] == [p.total_points for p in b.participants]


@given(
    mult=multipliers,
    weight=weights,
    quality=qualities,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=30)
def test_increasing_quality_never_decreases_points(mult, weight, quality) -> None:
    """A higher quality rating for the same task cannot reduce that task's points."""
    p_in = ParticipantInput(user_id="u1", display_name="U")
    base = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)],
        participants=[p_in],
        tasks=[
            _task_input("u1", weight=weight, quality=quality, due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
        ],
    )
    higher_quality = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)],
        participants=[p_in],
        tasks=[
            _task_input("u1", weight=weight, quality=min(quality + 1, 5), due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
        ],
    )
    a = compute_project_score(base)
    b = compute_project_score(higher_quality)
    assert b.participants[0].total_points >= a.participants[0].total_points


@given(
    participants=participants,
    weight=weights,
    quality=qualities,
    mult=multipliers,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=30)
def test_add_task_for_one_does_not_change_others(participants, weight, quality, mult) -> None:
    """Adding a new task for participant u1 does not change u2's points."""
    if len(participants) < 2:
        return
    u1 = participants[0].user_id
    u2 = participants[1].user_id
    base_tasks = [
        _task_input(u2, weight=weight, quality=quality, due=date(2025, 1, 10),
                    submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
    ]
    extra = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)],
        participants=participants,
        tasks=base_tasks + [_task_input(u1, weight=weight, quality=quality, due=date(2025, 1, 10),
                                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc))],
    )
    base = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)],
        participants=participants,
        tasks=base_tasks,
    )
    a = compute_project_score(base)
    b = compute_project_score(extra)
    a_u2 = next(p.total_points for p in a.participants if p.user_id == u2)
    b_u2 = next(p.total_points for p in b.participants if p.user_id == u2)
    assert a_u2 == b_u2


@given(
    participants=participants,
    weight=weights,
    quality=qualities,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=20)
def test_shares_sum_to_100(participants, weight, quality) -> None:
    tasks = [
        _task_input(p.user_id, weight=weight, quality=quality, due=date(2025, 1, 10),
                    submitted=datetime(2025, 1, 10, tzinfo=timezone.utc))
        for p in participants
    ]
    inputs = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=participants,
        tasks=tasks,
    )
    result = compute_project_score(inputs)
    total_pct = sum((p.share_pct for p in result.participants), start=Decimal("0"))
    if result.total_points > 0:
        # Allow ±0.01 rounding for 6-decimal accumulation.
        assert abs(total_pct - Decimal("100")) < Decimal("0.5")


@given(
    participants=participants,
    weight=weights,
    quality=qualities,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=20)
def test_order_independent_of_task_input_order(participants, weight, quality) -> None:
    if len(participants) < 2:
        return
    tasks = [
        _task_input(p.user_id, weight=weight, quality=quality, due=date(2025, 1, 10),
                    submitted=datetime(2025, 1, 10, tzinfo=timezone.utc))
        for p in participants
    ]
    inputs_a = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=participants,
        tasks=list(tasks),
    )
    inputs_b = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=participants,
        tasks=list(reversed(tasks)),
    )
    a = compute_project_score(inputs_a)
    b = compute_project_score(inputs_b)
    assert [p.user_id for p in a.suggested_order] == [p.user_id for p in b.suggested_order]


@given(
    participants=participants,
    weight=weights,
    quality=qualities,
)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=20)
def test_ranking_is_deterministic(participants, weight, quality) -> None:
    """Repeated computation yields the same order."""
    tasks = [
        _task_input(p.user_id, weight=weight, quality=quality, due=date(2025, 1, 10),
                    submitted=datetime(2025, 1, 10, tzinfo=timezone.utc))
        for p in participants
    ]
    inputs = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=participants,
        tasks=tasks,
    )
    a = compute_project_score(inputs)
    b = compute_project_score(inputs)
    assert [p.user_id for p in a.suggested_order] == [p.user_id for p in b.suggested_order]


def test_adjustments_apply_to_correct_user() -> None:
    """Adding an adjustment for u1 doesn't change u2."""
    p1 = ParticipantInput(user_id="u1", display_name="A")
    p2 = ParticipantInput(user_id="u2", display_name="B")
    base = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=[p1, p2],
        tasks=[
            _task_input("u1", weight=5, quality=5, due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
            _task_input("u2", weight=5, quality=5, due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
        ],
    )
    adjusted = ProjectInputs(
        project_id="p",
        settings=_ts(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1"))],
        participants=[p1, p2],
        tasks=[
            _task_input("u1", weight=5, quality=5, due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
            _task_input("u2", weight=5, quality=5, due=date(2025, 1, 10),
                        submitted=datetime(2025, 1, 10, tzinfo=timezone.utc)),
        ],
        adjustments=[AdjustmentInput(user_id="u1", delta=Decimal("10"), reason="bonus", author_user_id="leader",
                                     created_at=datetime.now(tz=timezone.utc))],
    )
    base_r = compute_project_score(base)
    adj_r = compute_project_score(adjusted)
    a_u2 = next(p.total_points for p in base_r.participants if p.user_id == "u2")
    b_u2 = next(p.total_points for p in adj_r.participants if p.user_id == "u2")
    assert a_u2 == b_u2
    a_u1 = next(p.total_points for p in base_r.participants if p.user_id == "u1")
    b_u1 = next(p.total_points for p in adj_r.participants if p.user_id == "u1")
    assert b_u1 == a_u1 + Decimal("10")
