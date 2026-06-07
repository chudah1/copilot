import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_gap import MonitoringGap

logger = logging.getLogger(__name__)

VALID_SOURCES = frozenset({
    "gemini_news",
    "edgar",
    "news_search",
    "llm_classifier",
    "embedding",
})


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
    gap = MonitoringGap(
        thesis_id=thesis_id,
        source=source,
        error_message=str(error_message)[:2000],
        run_id=run_id,
        failed_at=datetime.now(timezone.utc),
    )
    db.add(gap)
    logger.info("Monitoring gap recorded: source=%s thesis=%s", source, thesis_id)
