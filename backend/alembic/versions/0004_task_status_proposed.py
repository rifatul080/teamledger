"""task status 'proposed' value

Revision ID: 0004_task_status_proposed
Revises: 0003_milestone_completed_at
Create Date: 2026-09-21
"""
from __future__ import annotations

from alembic import op


revision = "0004_task_status_proposed"
down_revision = "0003_milestone_completed_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("task_status_check", type_="check")
        batch_op.create_check_constraint(
            "task_status_check",
            "status in ('proposed','todo','in_progress','in_review','needs_rework','done')",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("task_status_check", type_="check")
        batch_op.create_check_constraint(
            "task_status_check",
            "status in ('todo','in_progress','in_review','needs_rework','done')",
        )
