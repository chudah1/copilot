import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import async_session
from app.models.monitoring_gap import MonitoringGap

logger = logging.getLogger(__name__)

VALID_SOURCES = frozenset({
    "gemini_news",
    "edgar",
    "news_search",
    "llm_classifier",
    "embedding",
})

_SQLITE_LOCK_RETRY_ATTEMPTS = 3
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.15


def _is_sqlite_locked_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def _gap_session_factory(db: AsyncSession):
    bind = getattr(db, "bind", None)
    if bind is None:
        return async_session
    return async_sessionmaker(bind, class_=AsyncSession, expire_on_commit=False)


async def write_monitoring_gap(
    db: AsyncSession,
    thesis_id: uuid.UUID | None,
    source: str,
    error_message: str,
    run_id: str,
) -> None:
    if source not in VALID_SOURCES:
        logger.warning("Unknown gap source %r — skipping gap write", source)
        return

    # Use an isolated session so a best-effort telemetry write cannot poison the
    # caller's main transaction if SQLite is locked in local dev.
    session_factory = _gap_session_factory(db)

    for attempt in range(_SQLITE_LOCK_RETRY_ATTEMPTS):
        async with session_factory() as gap_db:
            gap = MonitoringGap(
                thesis_id=thesis_id,
                source=source,
                error_message=str(error_message)[:2000],
                run_id=run_id,
                failed_at=datetime.now(timezone.utc),
            )
            gap_db.add(gap)
            try:
                await gap_db.commit()
                logger.info("Monitoring gap recorded: source=%s thesis=%s", source, thesis_id)
                return
            except OperationalError as exc:
                await gap_db.rollback()
                if not _is_sqlite_locked_error(exc):
                    logger.warning(
                        "Monitoring gap write failed: source=%s thesis=%s error=%s",
                        source,
                        thesis_id,
                        exc,
                    )
                    return
                if attempt == _SQLITE_LOCK_RETRY_ATTEMPTS - 1:
                    logger.warning(
                        "Monitoring gap write skipped after sqlite lock retries: source=%s thesis=%s",
                        source,
                        thesis_id,
                    )
                    return
        await asyncio.sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS * (attempt + 1))
