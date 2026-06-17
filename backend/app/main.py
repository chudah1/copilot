from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

from app.config import settings
from app.database import engine, Base
from app.sqlite_dev_compat import ensure_sqlite_dev_compatibility
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
    coverage_pass,
    digest,
    quarterly_review,
    quarterly_review_response,
    password_reset_token,
    onboarding_state,
    onboarding_draft,
)
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler


def _cors_origins() -> list[str]:
    origins = {
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    }
    for url in filter(None, [settings.frontend_url, settings.app_url]):
        origins.add(url.rstrip("/"))
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.port:
            if parsed.hostname == "localhost":
                origins.add(f"{parsed.scheme}://127.0.0.1:{parsed.port}")
            if parsed.hostname == "127.0.0.1":
                origins.add(f"{parsed.scheme}://localhost:{parsed.port}")
    return sorted(origins)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite local dev
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ensure_sqlite_dev_compatibility)
    scheduler_started = False
    if settings.enable_scheduler:
        setup_scheduler()
        scheduler_started = True
    yield
    if scheduler_started:
        shutdown_scheduler()


app = FastAPI(title="penKeep", version="0.1.0", lifespan=lifespan)
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

from app.routes.research import router as research_router
app.include_router(research_router)

from app.routes.waitlist import router as waitlist_router
app.include_router(waitlist_router)

from app.routes.presale import router as presale_router
app.include_router(presale_router)


@app.get("/health")
async def health():
    # Surface background-job health so a silently failing job (which would leave
    # the dashboard stale) is visible to uptime monitoring. Always 200 so the
    # platform health check doesn't restart-loop on a single bad job run.
    from app.jobs.scheduler import JOB_HEALTH

    failed = sorted(job_id for job_id, h in JOB_HEALTH.items() if h.get("status") in ("error", "missed"))
    return {
        "status": "degraded" if failed else "ok",
        "failed_jobs": failed,
        "jobs": JOB_HEALTH,
    }
