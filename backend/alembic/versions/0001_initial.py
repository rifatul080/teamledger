"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    def _ts_default() -> sa.TextClause | str:
        # SQLite can't use server_default with timezone-aware timestamps portably.
        if is_sqlite:
            return ""
        return sa.text("now()")

    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "teams",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role in ('leader','member')", name="membership_role_check"),
        sa.UniqueConstraint("user_id", "team_id", name="ix_membership_user_team"),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_team_id", "memberships", ["team_id"])

    op.create_table(
        "invitations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("invited_by_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('link','in_app')", name="invitation_kind_check"),
        sa.UniqueConstraint("token", name="ix_invitation_token"),
    )
    op.create_index("ix_invitations_team_id", "invitations", ["team_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("family_id", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("created_at_db", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at_db", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="ix_prt_token"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("target_venue", sa.String(255), nullable=True),
        sa.Column("venue_kind", sa.String(16), nullable=True),
        sa.Column("submission_deadline", sa.Date, nullable=True),
        sa.Column("contrib_visibility", sa.String(16), nullable=False, server_default="leader_only"),
        sa.Column("reviewer_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_by", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('general','paper')", name="project_kind_check"),
        sa.CheckConstraint(
            "venue_kind is null or venue_kind in ('journal','conference')",
            name="project_venue_kind_check",
        ),
        sa.CheckConstraint(
            "contrib_visibility in ('leader_only','all')",
            name="project_vis_check",
        ),
    )
    op.create_index("ix_projects_team_id", "projects", ["team_id"])

    op.create_table(
        "timeliness_settings",
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("on_time_band_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mild_band_days", sa.Integer, nullable=False, server_default="2"),
        sa.Column("medium_band_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("late_mild", sa.Float, nullable=False, server_default="0.9"),
        sa.Column("late_medium", sa.Float, nullable=False, server_default="0.75"),
        sa.Column("late_severe", sa.Float, nullable=False, server_default="0.5"),
    )

    op.create_table(
        "project_participants",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="ix_pp_project_user"),
    )
    op.create_index("ix_project_participants_project_id", "project_participants", ["project_id"])
    op.create_index("ix_project_participants_user_id", "project_participants", ["user_id"])

    op.create_table(
        "goals",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goals_project_id", "goals", ["project_id"])

    op.create_table(
        "milestones",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("goal_id", sa.String(32), sa.ForeignKey("goals.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_milestones_goal_id", "milestones", ["goal_id"])

    op.create_table(
        "credit_categories",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("label", sa.String(120), nullable=False),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("milestone_id", sa.String(32), sa.ForeignKey("milestones.id"), nullable=False),
        sa.Column("assignee_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_code", sa.String(64), sa.ForeignKey("credit_categories.code"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(4000), nullable=True),
        sa.Column("weight", sa.Integer, nullable=False, server_default="5"),
        sa.Column("est_hours", sa.Integer, nullable=False, server_default="4"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="todo"),
        sa.Column("points_awarded", sa.Numeric(20, 6), nullable=True),
        sa.Column("first_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("proposer_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("split_from_task_id", sa.String(32), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('todo','in_progress','in_review','needs_rework','done')",
            name="task_status_check",
        ),
        sa.CheckConstraint("weight between 1 and 10", name="task_weight_check"),
    )
    op.create_index("ix_tasks_milestone_id", "tasks", ["milestone_id"])
    op.create_index("ix_tasks_assignee_user_id", "tasks", ["assignee_user_id"])

    op.create_table(
        "task_reviews",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("reviewer_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quality", sa.Integer, nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("note", sa.String(2000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision in ('accept','reject')", name="taskreview_decision_check"),
        sa.CheckConstraint("quality between 1 and 5", name="taskreview_quality_check"),
    )
    op.create_index("ix_task_reviews_task_id", "task_reviews", ["task_id"])
    op.create_index("ix_task_reviews_reviewer_user_id", "task_reviews", ["reviewer_user_id"])

    op.create_table(
        "task_submissions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False, server_default="1"),
        sa.Column("submitted_by_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_submissions_task_id", "task_submissions", ["task_id"])

    op.create_table(
        "category_multipliers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("category_code", sa.String(64), sa.ForeignKey("credit_categories.code"), nullable=False),
        sa.Column("multiplier", sa.Numeric(6, 3), nullable=False, server_default="1.000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "category_code", name="uq_proj_cat"),
    )

    op.create_table(
        "score_adjustments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delta", sa.Numeric(20, 6), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("author_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "author_order_snapshots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("payload_json", sa.String(200_000), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_by", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "author_order_positions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("snapshot_id", sa.String(32), sa.ForeignKey("author_order_snapshots.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_aop_snapshot_position",
        "author_order_positions",
        ["snapshot_id", "position"],
        unique=True,
    )

    op.create_table(
        "weekly_plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weekly_cap_hours", sa.Integer, nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weekly_cap_hours between 0 and 168", name="weekly_plan_cap_check"),
    )

    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("weekly_plan_id", sa.String(32), sa.ForeignKey("weekly_plans.id"), nullable=False),
        sa.Column("weekday", sa.Integer, nullable=False),
        sa.Column("start_minute", sa.Integer, nullable=False),
        sa.Column("end_minute", sa.Integer, nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weekday between 0 and 6", name="schedule_slot_weekday_check"),
        sa.CheckConstraint("end_minute > start_minute", name="schedule_slot_range_check"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("sender_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("seq", sa.BigInteger, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("mentions", sa.String(2000), nullable=False, server_default=""),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_msg_team_seq", "chat_messages", ["team_id", "seq"])
    op.create_index("ix_msg_sender", "chat_messages", ["sender_user_id"])

    op.create_table(
        "message_reads",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("last_read_seq", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_msgread_user_team", "message_reads", ["user_id", "team_id"])

    op.create_table(
        "files",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("folder", sa.String(120), nullable=False, server_default="/"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("current_version_id", sa.String(32), nullable=True),
        sa.Column("uploader_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "team_id", "folder", "name", name="ix_file_team_folder_name"
        ),
    )
    op.create_index("ix_files_team_id", "files", ["team_id"])

    op.create_table(
        "file_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("file_id", sa.String(32), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploader_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("file_id", "version_no", name="ix_fv_file_version"),
    )
    op.create_index("ix_file_versions_file_id", "file_versions", ["file_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type in ('assignment','review_result','mention','deadline_3d','deadline_1d','overdue')",
            name="notification_type_check",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "notification_keys",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("task_id", sa.String(32), nullable=False),
        sa.Column("recipient_id", sa.String(32), nullable=False),
        sa.Column("bucket", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "task_id", "recipient_id", "bucket", name="uq_notif_key"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("actor_user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.String(32), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("project_id", sa.String(32), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("subject_kind", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_subject_id", "audit_events", ["subject_id"])
    op.create_index("ix_audit_events_at", "audit_events", ["at"])


def downgrade() -> None:
    # Drop in reverse dependency order.
    for tbl in [
        "audit_events",
        "notification_keys",
        "notifications",
        "file_versions",
        "files",
        "message_reads",
        "chat_messages",
        "schedule_slots",
        "weekly_plans",
        "author_order_positions",
        "author_order_snapshots",
        "score_adjustments",
        "category_multipliers",
        "task_submissions",
        "task_reviews",
        "tasks",
        "credit_categories",
        "milestones",
        "goals",
        "project_participants",
        "timeliness_settings",
        "projects",
        "password_reset_tokens",
        "refresh_sessions",
        "invitations",
        "memberships",
        "teams",
        "users",
    ]:
        op.drop_table(tbl)
