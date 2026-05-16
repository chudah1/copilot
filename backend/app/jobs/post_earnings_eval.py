"""Daily job: run monitoring for tickers that reported earnings yesterday."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.database import async_session
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.check_now import run_check_now

logger = logging.getLogger(__name__)


async def run_post_earnings_evaluation() -> None:
    logger.info("Running post-earnings evaluation job")
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_end = yesterday_start + timedelta(days=1)

    async with async_session() as db:
        # Find tickers that reported yesterday
        earnings_result = await db.execute(
            select(EarningsCalendar).where(
                EarningsCalendar.report_date >= yesterday_start,
                EarningsCalendar.report_date < yesterday_end,
            )
        )
        reported = earnings_result.scalars().all()

    if not reported:
        logger.info("No earnings reported yesterday, skipping")
        return

    reported_tickers = {e.ticker for e in reported}
    logger.info("Post-earnings evaluation for: %s", ", ".join(reported_tickers))

    async with async_session() as db:
        # Find all user holdings + active theses for these tickers
        holdings_result = await db.execute(
            select(Holding, Thesis)
            .join(Thesis, and_(
                Thesis.holding_id == Holding.id,
                Thesis.status.in_(["active", "needs_review"]),
            ))
            .where(Holding.ticker.in_(reported_tickers))
        )
        pairs = holdings_result.all()

        evaluated = 0
        for holding, thesis in pairs:
            try:
                result = await run_check_now(holding, thesis, db)
                if result.events_created > 0:
                    logger.info(
                        "Post-earnings: %d events for %s (user %s)",
                        result.events_created,
                        holding.ticker,
                        holding.user_id,
                    )
                evaluated += 1
            except Exception as exc:
                logger.error(
                    "Post-earnings eval failed for %s / user %s: %s",
                    holding.ticker,
                    holding.user_id,
                    exc,
                )

    logger.info("Post-earnings evaluation complete: %d holdings evaluated", evaluated)
