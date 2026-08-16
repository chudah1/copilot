import logging

from sqlalchemy import inspect, text


logger = logging.getLogger(__name__)


def ensure_sqlite_dev_compatibility(conn) -> None:
    if conn.dialect.name != "sqlite":
        return

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "onboarding_completed_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed_at DATETIME"))
            logger.info("Added missing users.onboarding_completed_at column for local SQLite compatibility")
        if "last_seen_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_seen_at DATETIME"))
            logger.info("Added missing users.last_seen_at column for local SQLite compatibility")

    if "holdings" in tables:
        holding_columns = {column["name"] for column in inspector.get_columns("holdings")}
        if "average_cost_native" not in holding_columns:
            conn.execute(text("ALTER TABLE holdings ADD COLUMN average_cost_native NUMERIC(18, 4)"))
            logger.info("Added missing holdings.average_cost_native column for local SQLite compatibility")
        if "last_monitored_at" not in holding_columns:
            conn.execute(text("ALTER TABLE holdings ADD COLUMN last_monitored_at DATETIME"))
            logger.info("Added missing holdings.last_monitored_at column for local SQLite compatibility")

    if "thesis_signals" in tables:
        thesis_signal_columns = {column["name"] for column in inspector.get_columns("thesis_signals")}
        if "last_fired_at" not in thesis_signal_columns:
            conn.execute(text("ALTER TABLE thesis_signals ADD COLUMN last_fired_at DATETIME"))
            logger.info("Added missing thesis_signals.last_fired_at column for local SQLite compatibility")
        if "consecutive_ignores" not in thesis_signal_columns:
            conn.execute(
                text("ALTER TABLE thesis_signals ADD COLUMN consecutive_ignores INTEGER NOT NULL DEFAULT 0")
            )
            logger.info(
                "Added missing thesis_signals.consecutive_ignores column for local SQLite compatibility"
            )
        if "label_refreshed_at" not in thesis_signal_columns:
            conn.execute(text("ALTER TABLE thesis_signals ADD COLUMN label_refreshed_at DATETIME"))
            logger.info("Added missing thesis_signals.label_refreshed_at column for local SQLite compatibility")

    if "thesis_claims" in tables:
        thesis_claim_columns = {column["name"] for column in inspector.get_columns("thesis_claims")}
        if "embedding_text" not in thesis_claim_columns:
            conn.execute(text("ALTER TABLE thesis_claims ADD COLUMN embedding_text TEXT"))
            logger.info("Added missing thesis_claims.embedding_text column for local SQLite compatibility")
        if "embedding" not in thesis_claim_columns:
            conn.execute(text("ALTER TABLE thesis_claims ADD COLUMN embedding JSON"))
            logger.info("Added missing thesis_claims.embedding column for local SQLite compatibility")
        if "embedded_at" not in thesis_claim_columns:
            conn.execute(text("ALTER TABLE thesis_claims ADD COLUMN embedded_at DATETIME"))
            logger.info("Added missing thesis_claims.embedded_at column for local SQLite compatibility")

    if "theses" in tables:
        thesis_columns = {column["name"] for column in inspector.get_columns("theses")}
        if "health_score" not in thesis_columns:
            conn.execute(text("ALTER TABLE theses ADD COLUMN health_score INTEGER"))
            logger.info("Added missing theses.health_score column for local SQLite compatibility")
        if "health_label" not in thesis_columns:
            conn.execute(text("ALTER TABLE theses ADD COLUMN health_label VARCHAR(10)"))
            logger.info("Added missing theses.health_label column for local SQLite compatibility")

    if "monitoring_events" in tables:
        monitoring_event_columns = {column["name"] for column in inspector.get_columns("monitoring_events")}
        if "story_anchor" not in monitoring_event_columns:
            conn.execute(text("ALTER TABLE monitoring_events ADD COLUMN story_anchor VARCHAR(255)"))
            logger.info("Added missing monitoring_events.story_anchor column for local SQLite compatibility")

    if "thesis_health_snapshots" not in tables:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS thesis_health_snapshots ("
            "id TEXT PRIMARY KEY, "
            "thesis_id TEXT NOT NULL REFERENCES theses(id) ON DELETE CASCADE, "
            "score INTEGER NOT NULL, "
            "label VARCHAR(10) NOT NULL, "
            "computed_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        ))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_thesis_health_snapshots_thesis_id ON thesis_health_snapshots(thesis_id)")
        )
        logger.info("Created thesis_health_snapshots table for local SQLite compatibility")

    if "founding_orders" not in tables:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS founding_orders ("
            "stripe_session_id TEXT PRIMARY KEY, "
            "email VARCHAR(255) NOT NULL, "
            "tier VARCHAR(32) NOT NULL, "
            "amount INTEGER NOT NULL, "
            "currency VARCHAR(8) NOT NULL, "
            "status VARCHAR(16) NOT NULL DEFAULT 'pending', "
            "created_at DATETIME NOT NULL, "
            "paid_at DATETIME)"
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_founding_orders_status ON founding_orders(status)"))
        logger.info("Created founding_orders table for local SQLite compatibility")

    if "founding_reservations" not in tables:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS founding_reservations ("
            "email VARCHAR(255) PRIMARY KEY, "
            "tier VARCHAR(32) NOT NULL, "
            "created_at DATETIME NOT NULL)"
        ))
        logger.info("Created founding_reservations table for local SQLite compatibility")

    if "evidence_chunks" not in tables:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS evidence_chunks ("
            "id TEXT PRIMARY KEY, "
            "thesis_id TEXT REFERENCES theses(id), "
            "holding_id TEXT REFERENCES holdings(id), "
            "ticker VARCHAR(20), "
            "source_type VARCHAR(50) NOT NULL, "
            "source_id VARCHAR(255), "
            "chunk_type VARCHAR(50) NOT NULL, "
            "chunk_index INTEGER NOT NULL DEFAULT 0, "
            "chunk_text TEXT NOT NULL, "
            "metadata_json JSON, "
            "embedding JSON, "
            "embedded_at DATETIME, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evidence_chunks_holding_id ON evidence_chunks(holding_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evidence_chunks_source_id ON evidence_chunks(source_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evidence_chunks_source_type ON evidence_chunks(source_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evidence_chunks_thesis_id ON evidence_chunks(thesis_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evidence_chunks_ticker ON evidence_chunks(ticker)"))
        logger.info("Created evidence_chunks table for local SQLite compatibility")

    if "onboarding_states" in tables:
        ob_columns = {column["name"] for column in inspector.get_columns("onboarding_states")}
        for col in ("drafts_generated_at", "drafts_reviewed_at", "wizard_skipped_at", "wizard_completed_at"):
            if col not in ob_columns:
                conn.execute(text(f"ALTER TABLE onboarding_states ADD COLUMN {col} DATETIME"))
                logger.info("Added missing onboarding_states.%s column for local SQLite compatibility", col)
        if "investor_profile" not in ob_columns:
            conn.execute(text("ALTER TABLE onboarding_states ADD COLUMN investor_profile VARCHAR(32)"))
            logger.info("Added missing onboarding_states.investor_profile column for local SQLite compatibility")
        if "reengagement_email_sent_at" not in ob_columns:
            conn.execute(text("ALTER TABLE onboarding_states ADD COLUMN reengagement_email_sent_at DATETIME"))
            logger.info("Added missing onboarding_states.reengagement_email_sent_at column for local SQLite compatibility")

    if "digests" in tables:
        digest_columns = {column["name"] for column in inspector.get_columns("digests")}
        if "reviewed_at" not in digest_columns:
            conn.execute(text("ALTER TABLE digests ADD COLUMN reviewed_at DATETIME"))
            logger.info("Added missing digests.reviewed_at column for local SQLite compatibility")


def bootstrap_local_sqlite_alembic_head(conn, metadata, head_revision: str | None) -> bool:
    if conn.dialect.name != "sqlite" or not head_revision:
        return False

    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        return False

    app_tables = set(metadata.tables)
    if not tables.intersection(app_tables):
        return False

    metadata.create_all(conn)
    ensure_sqlite_dev_compatibility(conn)
    conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:head_revision)"),
        {"head_revision": head_revision},
    )
    logger.warning(
        "Stamped existing local SQLite schema at Alembic head %s to avoid replaying migrations over create_all state",
        head_revision,
    )
    return True
