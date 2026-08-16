"""Add open loop dismissals table

Revision ID: 20260810_open_loops
Revises: 20260725_soak_id_fix
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260810_open_loops"
down_revision = "20260725_soak_id_fix"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "open_loop_dismissals" in existing_tables:
        return

    op.create_table(
        "open_loop_dismissals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("loop_key", sa.String(length=255), nullable=False),
        sa.Column("dismissed_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "loop_key", name="uq_open_loop_dismissals_user_loop_key"),
    )
    op.create_index("ix_open_loop_dismissals_user_id", "open_loop_dismissals", ["user_id"], unique=False)
    op.create_index("ix_open_loop_dismissals_loop_key", "open_loop_dismissals", ["loop_key"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "open_loop_dismissals" not in existing_tables:
        return
    indexes = {index["name"] for index in inspector.get_indexes("open_loop_dismissals")}
    for name in ("ix_open_loop_dismissals_user_id", "ix_open_loop_dismissals_loop_key"):
        if name in indexes:
            op.drop_index(name, table_name="open_loop_dismissals")
    op.drop_table("open_loop_dismissals")
