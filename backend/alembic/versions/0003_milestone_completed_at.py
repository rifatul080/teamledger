"""milestone.completed_at

Revision ID: 0003_milestone_completed_at
Revises: 0002_seed_credit
Create Date: 2026-09-21 14:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_milestone_completed_at"
down_revision = "0002_seed_credit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "milestones",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("milestones", "completed_at")
