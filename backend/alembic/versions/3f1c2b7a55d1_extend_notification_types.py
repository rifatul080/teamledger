"""extend_notification_types

Align the notifications CHECK constraint with the activity vocabulary used by
the assignment/mention triggers and the frontend ActivityKind union. The legacy
scheduler values stay valid so historical rows keep working.

Revision ID: 3f1c2b7a55d1
Revises: 2d0c9b00b439
Create Date: 2026-09-27
"""
from collections.abc import Sequence

from alembic import op

revision: str = '3f1c2b7a55d1'
down_revision: str | None = '2d0c9b00b439'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY = (
    "'assignment','review_result','mention','deadline_3d','deadline_1d','overdue'"
)
_EXTENDED = (
    "'assignment','review_result','mention','deadline_3d','deadline_1d','overdue',"
    "'task_assigned','task_reviewed','milestone','member','system'"
)


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("notification_type_check", type_="check")
        batch_op.create_check_constraint(
            "notification_type_check", f"type in ({_EXTENDED})"
        )


def downgrade() -> None:
    # Normalise rows to the legacy vocabulary first, or the CHECK fails.
    op.execute("UPDATE notifications SET type='assignment' WHERE type='task_assigned'")
    op.execute("UPDATE notifications SET type='review_result' WHERE type='task_reviewed'")
    op.execute("UPDATE notifications SET type='mention' WHERE type='milestone'")
    op.execute("UPDATE notifications SET type='system' WHERE type IN ('member', 'system')")
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("notification_type_check", type_="check")
        batch_op.create_check_constraint(
            "notification_type_check", f"type in ({_LEGACY})"
        )
