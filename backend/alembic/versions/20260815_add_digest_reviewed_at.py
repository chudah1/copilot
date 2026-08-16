"""add digest reviewed timestamp

Revision ID: 20260815_add_digest_reviewed_at
Revises: 20260811_add_dashboard_coach_advices
Create Date: 2026-08-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260815_add_digest_reviewed_at"
down_revision: str | None = "20260811_add_dashboard_coach_advices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("digests", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("digests", "reviewed_at")
