"""CRediT taxonomy + per-project category multipliers."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class CRediTCategory(Base):
    __tablename__ = "credit_categories"
    __table_args__ = (UniqueConstraint("code", name="uq_credit_code"),)

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)


class CategoryMultiplier(Base, TimestampMixin):
    __tablename__ = "category_multipliers"
    __table_args__ = (UniqueConstraint("project_id", "category_code", name="uq_proj_cat"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), nullable=False, index=True)
    category_code: Mapped[str] = mapped_column(String(64), ForeignKey("credit_categories.code"), nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=Decimal("1.000"))
