import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter
from sqlalchemy import inspect, text

from app.config import settings
from app.database import engine, Base
from app.models import (  # noqa: F401
    user,
    broker_connection,
    holding,
    thesis,
    thesis_decomposition,
    thesis_claim,
    thesis_entity,
    thesis_signal,
    thesis_review,
    monitoring_event,
    digest,
    quarterly_review,
    quarterly_review_response,
    password_reset_token,
    onboarding_state,
    onboarding_draft,
)
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    origins = {
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    }
    if settings.frontend_url:
        origins.add(settings.frontend_url.rstrip("/"))
        parsed = urlparse(settings.frontend_url)
        if parsed.scheme in {"http", "https"} and parsed.port:
            if parsed.hostname == "localhost":
                origins.add(f"{parsed.scheme}://127.0.0.1:{parsed.port}")
            if parsed.hostname == "127.0.0.1":
                origins.add(f"{parsed.scheme}://localhost:{parsed.port}")
    return sorted(origins)


def _ensure_sqlite_dev_compatibility(conn) -> None:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite local dev
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_sqlite_dev_compatibility)
    scheduler_started = False
    if settings.enable_scheduler:
        setup_scheduler()
        scheduler_started = True
    yield
    if scheduler_started:
        shutdown_scheduler()


app = FastAPI(title="Copilot Investor", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.auth import router as auth_router
app.include_router(auth_router)

from app.routes.portfolio import router as portfolio_router
app.include_router(portfolio_router)

from app.routes.monitoring import router as monitoring_router
app.include_router(monitoring_router)

from app.routes.settings import router as settings_router
app.include_router(settings_router)

from app.routes.thesis import router as thesis_router
app.include_router(thesis_router)

from app.routes.digest import router as digest_router
app.include_router(digest_router)

from app.routes.onboarding import router as onboarding_router
app.include_router(onboarding_router)

from app.routes.quarterly_review import router as quarterly_review_router
app.include_router(quarterly_review_router)

from app.routes.notifications import router as notifications_router
app.include_router(notifications_router)

from app.routes.research import router as research_router
app.include_router(research_router)

from app.routes.waitlist import router as waitlist_router
app.include_router(waitlist_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
