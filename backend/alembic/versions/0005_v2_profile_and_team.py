"""v2 — profile pictures, theme, institution, email verification, team work type.

Revision ID: 0005_v2_profile_and_team
Revises: 0004_task_status_proposed
Create Date: 2025
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_v2_profile_and_team"
down_revision = "0004_task_status_proposed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite batch mode for portable ALTER TABLE support.
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("avatar_small", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("avatar_large", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("theme", sa.String(length=8), nullable=False, server_default="light"))
        b.add_column(sa.Column("institution", sa.String(length=255), nullable=True))
    with op.batch_alter_table("teams") as b:
        b.add_column(sa.Column("work_type", sa.String(length=32), nullable=True))
        b.add_column(sa.Column("category_preset", sa.String(length=32), nullable=True))
    op.create_table(
        "email_verification_tokens",
        sa.Column("token", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_verification_tokens")
    with op.batch_alter_table("teams") as b:
        b.drop_column("category_preset")
        b.drop_column("work_type")
    with op.batch_alter_table("users") as b:
        b.drop_column("institution")
        b.drop_column("theme")
        b.drop_column("avatar_large")
        b.drop_column("avatar_small")
        b.drop_column("email_verified")
