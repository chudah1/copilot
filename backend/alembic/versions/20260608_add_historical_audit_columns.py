"""add historical_audit columns to theses

Revision ID: 20260608_add_historical_audit
Revises: 20260607_add_monitoring_gap
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260608_add_historical_audit"
down_revision = "20260607_add_monitoring_gap"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("theses", sa.Column("historical_audit_status", sa.String(20), nullable=True))
    op.add_column("theses", sa.Column("historical_audit_results", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("theses", "historical_audit_results")
    op.drop_column("theses", "historical_audit_status")
