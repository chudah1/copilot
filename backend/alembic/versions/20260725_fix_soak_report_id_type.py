"""Fix monitoring_soak_reports.id column type

The original migration (20260713_soak_reports) created `id` as a plain
varchar(36) instead of `sa.Uuid()`, unlike every other UUID primary key
in this schema. On PostgreSQL the ORM's UUIDType maps to a native `uuid`
column and binds parameters as ::UUID, so comparing it against the
varchar column raised:

  operator does not exist: character varying = uuid

SQLite is unaffected (UUIDType degrades to String(36) there), which is
why this only surfaced against production Postgres.

Revision ID: 20260725_soak_id_fix
Revises: 20260715_claim_reviews
Create Date: 2026-07-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260725_soak_id_fix"
down_revision = "20260715_claim_reviews"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE monitoring_soak_reports "
        "ALTER COLUMN id TYPE uuid USING id::uuid"
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE monitoring_soak_reports "
        "ALTER COLUMN id TYPE varchar(36) USING id::varchar(36)"
    )
