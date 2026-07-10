import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, text

from app.sqlite_dev_compat import (
    bootstrap_local_sqlite_alembic_head,
    ensure_sqlite_dev_compatibility,
)

_migration_path = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260516_add_noise_suppression_to_signals.py"
)
_migration_spec = importlib.util.spec_from_file_location(
    "noise_suppression_migration",
    _migration_path,
)
assert _migration_spec is not None and _migration_spec.loader is not None
noise_suppression_migration = importlib.util.module_from_spec(_migration_spec)
_migration_spec.loader.exec_module(noise_suppression_migration)


def test_sqlite_dev_compatibility_adds_missing_signal_columns():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    preferences JSON
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE thesis_signals (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    signal_label TEXT,
                    signal_config_json JSON,
                    rationale TEXT,
                    confidence NUMERIC,
                    confirmation_required BOOLEAN,
                    user_confirmed BOOLEAN,
                    active BOOLEAN,
                    raw_extraction_json JSON,
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE holdings (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantity NUMERIC NOT NULL,
                    average_cost_basis NUMERIC NOT NULL,
                    currency TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE monitoring_events (
                    id TEXT PRIMARY KEY,
                    holding_id TEXT NOT NULL,
                    thesis_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )

        ensure_sqlite_dev_compatibility(conn)

        inspector = inspect(conn)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        thesis_signal_columns = {column["name"] for column in inspector.get_columns("thesis_signals")}
        holding_columns = {column["name"] for column in inspector.get_columns("holdings")}
        monitoring_event_columns = {column["name"] for column in inspector.get_columns("monitoring_events")}

        assert "onboarding_completed_at" in user_columns
        assert "last_fired_at" in thesis_signal_columns
        assert "consecutive_ignores" in thesis_signal_columns
        assert "average_cost_native" in holding_columns
        assert "last_monitored_at" in holding_columns
        assert "story_anchor" in monitoring_event_columns


def test_noise_suppression_migration_skips_existing_sqlite_columns(monkeypatch):
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE thesis_signals (
                    id TEXT PRIMARY KEY,
                    entity_id TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    last_fired_at DATETIME,
                    consecutive_ignores INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )

        ctx = MigrationContext.configure(conn)
        operations = Operations(ctx)
        monkeypatch.setattr(noise_suppression_migration, "op", operations)

        noise_suppression_migration.upgrade()

        inspector = inspect(conn)
        thesis_signal_columns = {column["name"] for column in inspector.get_columns("thesis_signals")}

        assert "last_fired_at" in thesis_signal_columns
        assert "consecutive_ignores" in thesis_signal_columns


def test_bootstrap_local_sqlite_alembic_head_stamps_existing_schema():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", String, primary_key=True),
        Column("email", String, nullable=False),
        Column("password_hash", String, nullable=False),
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
        )

        stamped = bootstrap_local_sqlite_alembic_head(conn, metadata, "test_head_revision")

        inspector = inspect(conn)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        alembic_tables = set(inspector.get_table_names())
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

        assert stamped is True
        assert "alembic_version" in alembic_tables
        assert "onboarding_completed_at" in user_columns
        assert version == "test_head_revision"
