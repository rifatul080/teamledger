"""seed credit categories

Revision ID: 0002_seed_credit
Revises: 0001_initial
Create Date: 2025-01-01 00:01:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_seed_credit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


CATEGORIES = [
    ("conceptualization", "Conceptualization"),
    ("data_curation", "Data curation"),
    ("formal_analysis", "Formal analysis"),
    ("funding_acquisition", "Funding acquisition"),
    ("investigation", "Investigation"),
    ("methodology", "Methodology"),
    ("project_administration", "Project administration"),
    ("resources", "Resources"),
    ("software", "Software"),
    ("supervision", "Supervision"),
    ("validation", "Validation"),
    ("visualization", "Visualization"),
    ("writing_original_draft", "Writing - original draft"),
    ("writing_review_editing", "Writing - review & editing"),
]


def upgrade() -> None:
    rows = [{"code": code, "label": label} for code, label in CATEGORIES]
    op.bulk_insert(sa.table(
        "credit_categories",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
    ), rows)


def downgrade() -> None:
    op.execute("DELETE FROM credit_categories WHERE code IN ("
               + ",".join(f"'{c[0]}'" for c in CATEGORIES)
               + ")")
