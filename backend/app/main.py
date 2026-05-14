import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    password_reset_token,
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
    if "users" not in tables:
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "onboarding_completed_at" not in user_columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed_at DATETIME"))
        logger.info("Added missing users.onboarding_completed_at column for local SQLite compatibility")


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


@app.get("/health")
async def health():
    return {"status": "ok"}
