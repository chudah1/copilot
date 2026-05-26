"""add health_score and health_label to theses

Revision ID: 20260527_thesis_health
Revises: 20260524_add_reengagement_column
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260527_thesis_health"
down_revision = "20260524_add_reengagement_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("theses", sa.Column("health_score", sa.Integer(), nullable=True))
    op.add_column("theses", sa.Column("health_label", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("theses", "health_label")
    op.drop_column("theses", "health_score")
