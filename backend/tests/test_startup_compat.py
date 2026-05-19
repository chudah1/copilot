from sqlalchemy import create_engine, inspect, text

from app.main import _ensure_sqlite_dev_compatibility


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

        _ensure_sqlite_dev_compatibility(conn)

        inspector = inspect(conn)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        thesis_signal_columns = {column["name"] for column in inspector.get_columns("thesis_signals")}

        assert "onboarding_completed_at" in user_columns
        assert "last_fired_at" in thesis_signal_columns
        assert "consecutive_ignores" in thesis_signal_columns
