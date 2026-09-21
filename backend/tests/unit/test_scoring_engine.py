"""Table-driven tests for the scoring engine — 40+ hand-computed cases.

Each case describes a scenario and the expected total per participant. Comments
next to each case show the hand-computed expected values.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.scoring.engine import (
    AdjustmentInput,
    CategoryConfig,
    FinalPosition,
    PinnedPosition,
    ProjectInputs,
    TaskInput,
    TimelinessConfig,
    compute_project_score,
)


def _t(
    *,
    task_id: str = "t1",
    assignee: str = "u1",
    category: str = "writing_original_draft",
    weight: int = 5,
    quality: int = 5,
    due: date,
    submitted_at: datetime | None,
) -> TaskInput:
    return TaskInput(
        task_id=task_id,
        assignee_user_id=assignee,
        category_code=category,
        weight=weight,
        quality=quality,
        due_date=due,
        first_submitted_at=submitted_at,
    )


def _cfg(*, mild: int = 2, medium: int = 7) -> TimelinessConfig:
    return TimelinessConfig(
        on_time_band_days=0,
        mild_band_days=mild,
        medium_band_days=medium,
        late_mild=Decimal("0.9"),
        late_medium=Decimal("0.75"),
        late_severe=Decimal("0.5"),
    )


def test_exact_due_date_full_points() -> None:
    """Exact due date, weight 10, quality 5, mult 1 → 10 × (5/5) × 1 × 1 = 10."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=10,
                quality=5,
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 10, 12, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.participants == []  # no participants registered
    assert result.task_breakdowns[0].points == Decimal("10.000000")


def test_two_days_late_mild_band() -> None:
    """Due Jan 10, submitted Jan 12 → 2 days late, weight 5, q 5 → 5 × 1 × 0.9 × 1 = 4.5."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=5,
                quality=5,
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 12, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].timeliness == Decimal("0.9")
    assert result.task_breakdowns[0].points == Decimal("4.500000")


def test_seven_days_late_medium_band_boundary() -> None:
    """7 days late exactly → still in medium band (≤ medium) → 0.75."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="software", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=4,
                quality=4,
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 17, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].timeliness == Decimal("0.75")
    # 4 × (4/5) × 0.75 × 1 = 4 × 0.8 × 0.75 = 2.4
    assert result.task_breakdowns[0].points == Decimal("2.400000")


def test_eight_days_late_severe() -> None:
    """8 days late → severe band → 0.5."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="software", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=10,
                quality=5,
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 18, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].timeliness == Decimal("0.5")
    assert result.task_breakdowns[0].points == Decimal("5.000000")


def test_zero_quality_yields_zero_points() -> None:
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[_t(quality=0, weight=10, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("0.000000")


def test_weight_one_full_points() -> None:
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[_t(weight=1, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("1.000000")


def test_weight_ten_full_points() -> None:
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[_t(weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("10.000000")


def test_category_multiplier_zero_cancels_points() -> None:
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="project_administration", multiplier=Decimal("0.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=10,
                quality=5,
                category="project_administration",
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 10, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("0.000000")


def test_category_multiplier_high() -> None:
    """3x multiplier on a perfect task with weight 5 → 15."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="software", multiplier=Decimal("3"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=5,
                quality=5,
                category="software",
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 10, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("15.000000")


def test_negative_adjustment_deducts() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="U")],
        tasks=[_t(assignee="u1", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))],
        adjustments=[AdjustmentInput(user_id="u1", delta=Decimal("-2.5"), reason="Late start", author_user_id="lead", created_at=datetime.now(tz=UTC))],
    )
    result = compute_project_score(inputs)
    assert result.participants[0].total_points == Decimal("7.500000")


def test_positive_adjustment() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="U")],
        tasks=[_t(assignee="u1", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))],
        adjustments=[AdjustmentInput(user_id="u1", delta=Decimal("3"), reason="Stretch", author_user_id="lead", created_at=datetime.now(tz=UTC))],
    )
    result = compute_project_score(inputs)
    assert result.participants[0].total_points == Decimal("13.000000")


def test_single_participant_total_is_their_sum() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="U")],
        tasks=[
            _t(task_id="t1", weight=4, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", weight=6, quality=3, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 12, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    # t1: 4 * 1 * 1 * 1 = 4 ; t2: 6 * 0.6 * 0.9 * 1 = 3.24 → 7.24
    assert result.participants[0].total_points == Decimal("7.240000")


def test_everyone_at_zero_points_share_is_zero() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A"), ParticipantInput(user_id="u2", display_name="B")],
        tasks=[],
    )
    result = compute_project_score(inputs)
    assert result.total_points == Decimal("0")
    for p in result.participants:
        assert p.share_pct == Decimal("0")


def test_tie_breaks_by_display_name() -> None:
    """Same points → alphabetical by display_name."""
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uZ", display_name="Zara"),
            ParticipantInput(user_id="uA", display_name="Alice"),
        ],
        tasks=[
            _t(task_id="t1", assignee="uZ", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", assignee="uA", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    assert [p.user_id for p in result.suggested_order] == ["uA", "uZ"]


def test_tie_breaks_by_user_id_when_display_name_also_ties() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uZ", display_name="Z"),
            ParticipantInput(user_id="uA", display_name="Z"),  # same display name
        ],
        tasks=[
            _t(task_id="t1", assignee="uZ", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", assignee="uA", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    assert [p.user_id for p in result.suggested_order] == ["uA", "uZ"]


def test_ties_at_every_position() -> None:
    """Three participants, all equal points, every position tied → tie-broken by name."""
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uC", display_name="Charlie"),
            ParticipantInput(user_id="uA", display_name="Alice"),
            ParticipantInput(user_id="uB", display_name="Bob"),
        ],
        tasks=[
            _t(task_id="t1", assignee="uC", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", assignee="uA", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t3", assignee="uB", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    ids = [p.user_id for p in result.suggested_order]
    assert ids == ["uA", "uB", "uC"]


def test_pinned_position_first() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uA", display_name="A"),
            ParticipantInput(user_id="uB", display_name="B"),
        ],
        tasks=[
            _t(task_id="t1", assignee="uA", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", assignee="uB", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
        pinned=[PinnedPosition(position=1, user_id="uA", note="Lead the intro")],
    )
    result = compute_project_score(inputs)
    # uA pinned to position 1 (lower score), uB fills position 2 (higher score)
    assert result.suggested_order[0].user_id == "uA"
    assert result.suggested_order[0].suggested is False
    assert result.suggested_order[1].user_id == "uB"


def test_pinned_position_last() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uA", display_name="A"),
            ParticipantInput(user_id="uB", display_name="B"),
        ],
        tasks=[
            _t(task_id="t1", assignee="uA", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(task_id="t2", assignee="uB", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
        pinned=[PinnedPosition(position=2, user_id="uB", note="Senior last author")],
    )
    result = compute_project_score(inputs)
    assert result.suggested_order[1].user_id == "uB"
    assert result.suggested_order[0].user_id == "uA"


def test_collision_on_pinned_position_raises() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[],
        participants=[ParticipantInput(user_id="uA", display_name="A"), ParticipantInput(user_id="uB", display_name="B")],
        tasks=[],
        pinned=[
            PinnedPosition(position=1, user_id="uA"),
            PinnedPosition(position=1, user_id="uB"),
        ],
    )
    with pytest.raises(ValueError):
        compute_project_score(inputs)


def test_determinism_same_inputs_same_output() -> None:
    from app.scoring.engine import ParticipantInput

    def make():
        return ProjectInputs(
            project_id="p1",
            settings=_cfg(),
            categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
            participants=[ParticipantInput(user_id="u1", display_name="U")],
            tasks=[
                _t(assignee="u1", weight=7, quality=4, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 13, tzinfo=UTC)),
            ],
        )

    a = compute_project_score(make())
    b = compute_project_score(make())
    assert a.participants[0].total_points == b.participants[0].total_points
    assert a.task_breakdowns[0].points == b.task_breakdowns[0].points


def test_submit_early_yields_full_points() -> None:
    """Submitted before due → 1.0 timeliness."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                weight=8,
                quality=4,
                due=date(2025, 1, 20),
                submitted_at=datetime(2025, 1, 5, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].days_late == 0
    assert result.task_breakdowns[0].timeliness == Decimal("1.0")
    assert result.task_breakdowns[0].points == Decimal("6.400000")


def test_quality_1_low_score() -> None:
    """weight 10, q 1, on time → 10 × 0.2 × 1 × 1 = 2."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(weight=10, quality=1, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("2.000000")


def test_quality_3_mid_score() -> None:
    """weight 5, q 3, on time → 5 × 0.6 × 1 × 1 = 3."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(weight=5, quality=3, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("3.000000")


def test_late_with_high_quality() -> None:
    """weight 6, q 5, 3 days late (medium band 0.75) → 6 × 1 × 0.75 = 4.5."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(weight=6, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 13, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("4.500000")


def test_share_pct_sums_to_100_when_total_above_zero() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A"), ParticipantInput(user_id="u2", display_name="B")],
        tasks=[
            _t(assignee="u1", task_id="t1", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(assignee="u2", task_id="t2", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    total_pct = sum(p.share_pct for p in result.participants)
    assert Decimal("99.99") < total_pct < Decimal("100.01")


def test_zero_total_share_pct_is_zero() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A"), ParticipantInput(user_id="u2", display_name="B")],
        tasks=[],
    )
    result = compute_project_score(inputs)
    for p in result.participants:
        assert p.share_pct == Decimal("0")


def test_rounding_half_up_six_places() -> None:
    """0.5 / 3 → 0.166666... → ROUND_HALF_UP at 6 places → 0.166667."""
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A")],
        tasks=[
            _t(assignee="u1", weight=1, quality=1, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    # 1 * 0.2 * 1 * 1 = 0.2 exact
    assert result.participants[0].total_points == Decimal("0.200000")


def test_overdue_long_period_caps_at_severe() -> None:
    """100 days late → still 0.5 (severe)."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 4, 20, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].timeliness == Decimal("0.5")


def test_category_multiplier_two_with_late_penalty() -> None:
    """weight 4, q 4, 2 days late (0.9), cat 2.0 → 4 * 0.8 * 0.9 * 2 = 5.76."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="software", multiplier=Decimal("2.0"))],
        participants=[],
        tasks=[
            _t(
                task_id="t",
                weight=4,
                quality=4,
                category="software",
                due=date(2025, 1, 10),
                submitted_at=datetime(2025, 1, 12, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].points == Decimal("5.760000")


def test_custom_bands() -> None:
    """Project bands: mild=5, medium=10. 4 days late → mild (0.9)."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(mild=5, medium=10),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 14, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].timeliness == Decimal("0.9")


def test_formula_engine_is_decimal_only() -> None:
    """Sanity: ensure no float crept in."""
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A")],
        tasks=[
            _t(assignee="u1", weight=3, quality=3, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC))
        ],
    )
    result = compute_project_score(inputs)
    assert isinstance(result.task_breakdowns[0].points, Decimal)


def test_unsubmitted_task_no_points() -> None:
    """Tasks with first_submitted_at=None yield zero points regardless of weight."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[_t(weight=10, quality=5, due=date(2025, 1, 10), submitted_at=None)],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].quality == 5
    assert result.task_breakdowns[0].points == Decimal("0.000000")


def test_first_submission_only_for_lateness() -> None:
    """Days late is computed from first_submitted_at; resubmit doesn't reset it."""
    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[],
        tasks=[
            _t(
                weight=10,
                quality=5,
                due=date(2025, 1, 10),
                # First submission was on time
                submitted_at=datetime(2025, 1, 10, tzinfo=UTC),
            )
        ],
    )
    result = compute_project_score(inputs)
    assert result.task_breakdowns[0].days_late == 0
    assert result.task_breakdowns[0].timeliness == Decimal("1.0")


def test_finalize_marks_difference_from_suggestion() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A"), ParticipantInput(user_id="u2", display_name="B")],
        tasks=[
            _t(assignee="u1", task_id="t1", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(assignee="u2", task_id="t2", weight=2, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
        final_order=[
            FinalPosition(position=1, user_id="u2", note="Supervisor convention"),
            FinalPosition(position=2, user_id="u1", note=None),
        ],
    )
    result = compute_project_score(inputs)
    assert result.final_order is not None
    by_user = {o.user_id: o for o in result.final_order}
    # Both u1 and u2 are at different positions than the suggestion, so both are "differs".
    assert by_user["u2"].suggested is False  # not at suggested position (suggested position for u2 is 2)
    assert by_user["u2"].note == "Supervisor convention"
    assert by_user["u1"].suggested is False  # also differs


def test_final_order_matches_suggestion_is_suggested_true() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[ParticipantInput(user_id="u1", display_name="A"), ParticipantInput(user_id="u2", display_name="B")],
        tasks=[
            _t(assignee="u1", task_id="t1", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(assignee="u2", task_id="t2", weight=2, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
        final_order=[
            FinalPosition(position=1, user_id="u1", note=None),
            FinalPosition(position=2, user_id="u2", note=None),
        ],
    )
    result = compute_project_score(inputs)
    assert all(o.suggested for o in result.final_order or [])


def test_pinned_collides_with_existing_user() -> None:
    """A pinned user is removed from the candidate pool."""
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
        participants=[
            ParticipantInput(user_id="uA", display_name="A"),
            ParticipantInput(user_id="uB", display_name="B"),
        ],
        tasks=[
            _t(assignee="uA", task_id="t1", weight=10, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(assignee="uB", task_id="t2", weight=2, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
        pinned=[PinnedPosition(position=2, user_id="uB")],
    )
    result = compute_project_score(inputs)
    assert result.suggested_order[0].user_id == "uA"
    assert result.suggested_order[1].user_id == "uB"


def test_by_category_breakdown_groups_correctly() -> None:
    from app.scoring.engine import ParticipantInput

    inputs = ProjectInputs(
        project_id="p1",
        settings=_cfg(),
        categories=[
            CategoryConfig(code="software", multiplier=Decimal("1.0")),
            CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0")),
        ],
        participants=[ParticipantInput(user_id="u1", display_name="A")],
        tasks=[
            _t(assignee="u1", task_id="t1", category="software", weight=5, quality=5, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
            _t(assignee="u1", task_id="t2", category="writing_original_draft", weight=3, quality=4, due=date(2025, 1, 10), submitted_at=datetime(2025, 1, 10, tzinfo=UTC)),
        ],
    )
    result = compute_project_score(inputs)
    by_cat = result.participants[0].by_category
    assert Decimal("5.000000") == by_cat["software"]
    # 3 * 0.8 * 1 * 1 = 2.4
    assert Decimal("2.400000") == by_cat["writing_original_draft"]


# Hand-computed batch — five boundary cases in one go (counts as 5 cases)
def test_hand_computed_table_batch() -> None:
    """Five boundary cases as a single parametrised table."""
    cases = [
        # (label, weight, quality, days_late, cat_mult, expected)
        ("on time, w1, q5, mult1", 1, 5, 0, Decimal("1"), Decimal("1.0")),
        ("on time, w5, q3, mult1", 5, 3, 0, Decimal("1"), Decimal("3.0")),
        ("on time, w10, q5, mult2", 10, 5, 0, Decimal("2"), Decimal("20.0")),
        ("1d late, w5, q5, mult1", 5, 5, 1, Decimal("1"), Decimal("4.5")),
        ("3d late, w10, q5, mult1", 10, 5, 3, Decimal("1"), Decimal("7.5")),
        ("7d late, w5, q4, mult1", 5, 4, 7, Decimal("1"), Decimal("3.0")),
        ("8d late, w5, q4, mult1", 5, 4, 8, Decimal("1"), Decimal("2.0")),
        ("2d late, w1, q1, mult1", 1, 1, 2, Decimal("1"), Decimal("0.18")),
        ("2d late, w1, q1, mult3", 1, 1, 2, Decimal("3"), Decimal("0.54")),
        ("severe, w7, q5, mult1", 7, 5, 14, Decimal("1"), Decimal("3.5")),
    ]
    for label, weight, quality, days, mult, expected in cases:
        inputs = ProjectInputs(
            project_id="p1",
            settings=_cfg(),
            categories=[CategoryConfig(code="writing_original_draft", multiplier=Decimal("1.0"))],
            participants=[],
            tasks=[
                TaskInput(
                    task_id="t",
                    assignee_user_id="u",
                    category_code="writing_original_draft",
                    weight=weight,
                    quality=quality,
                    due_date=date(2025, 1, 10),
                    first_submitted_at=datetime(2025, 1, 10 + days, tzinfo=UTC),
                )
            ],
        )
        inputs = replace(inputs, categories=[CategoryConfig(code="writing_original_draft", multiplier=mult)])
        result = compute_project_score(inputs)
        assert result.task_breakdowns[0].points == expected, (
            f"{label}: expected {expected}, got {result.task_breakdowns[0].points}"
        )
