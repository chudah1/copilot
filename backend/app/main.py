import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.models import user, broker_connection, holding, thesis, monitoring_event, digest  # noqa: F401
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables for SQLite local dev
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    setup_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Copilot Investor", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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


@app.get("/health")
async def health():
    return {"status": "ok"}
