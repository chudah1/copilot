"""Weekly job: refresh earnings calendar for all held tickers."""
import logging

from sqlalchemy import select

from app.database import async_session
from app.models.holding import Holding
from app.services.earnings_service import refresh_earnings_batch

logger = logging.getLogger(__name__)


async def run_earnings_refresh() -> None:
    logger.info("Starting weekly earnings calendar refresh")
    async with async_session() as db:
        result = await db.execute(select(Holding.ticker).distinct())
        tickers = [row[0] for row in result.all()]

    if not tickers:
        logger.info("No holdings found, skipping earnings refresh")
        return

    logger.info("Refreshing earnings for %d tickers", len(tickers))
    async with async_session() as db:
        await refresh_earnings_batch(db, tickers)
        await db.commit()

    logger.info("Earnings calendar refresh complete")
