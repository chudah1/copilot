import logging
import uuid
from datetime import datetime, timezone

from app.database import async_session
from app.services.soak_monitor import (
    SoakBasketEntry,
    active_thesis_basket,
    build_soak_report,
    persist_soak_report,
    soak_window_for_days,
)

logger = logging.getLogger(__name__)

SOAK_REPORT_DAYS = 5
SOAK_REPORT_TIMEZONE = "Europe/London"


async def run_monitoring_soak_report():
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    logger.info("Starting monitoring_soak_report run_id=%s", run_id)

    window_start, window_end = soak_window_for_days(
        days=SOAK_REPORT_DAYS,
        timezone_name=SOAK_REPORT_TIMEZONE,
    )

    async with async_session() as db:
        # Basket resolution happens inside the try so any failure still
        # persists an error snapshot instead of dying invisibly.
        basket: list[SoakBasketEntry] = []
        try:
            basket = await active_thesis_basket(db)
            report = await build_soak_report(
                db,
                basket=basket,
                start_at=window_start,
                end_at=window_end,
                timezone_name=SOAK_REPORT_TIMEZONE,
            )
            finished_at = datetime.now(timezone.utc)
            await persist_soak_report(
                db,
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                window_start=window_start,
                window_end=window_end,
                timezone_name=SOAK_REPORT_TIMEZONE,
                basket=basket,
                report=report,
                status="ok",
            )
            logger.info(
                "monitoring_soak_report complete run_id=%s summaries=%d unresolved=%d",
                run_id,
                len(report.summaries),
                len(report.unresolved),
            )
        except Exception as exc:
            logger.exception("monitoring_soak_report failed run_id=%s: %s", run_id, exc)
            finished_at = datetime.now(timezone.utc)
            try:
                await persist_soak_report(
                    db,
                    run_id=run_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    window_start=window_start,
                    window_end=window_end,
                    timezone_name=SOAK_REPORT_TIMEZONE,
                    basket=basket,
                    report=None,
                    status="error",
                    error_message=str(exc),
                )
            except Exception:
                logger.exception("monitoring_soak_report failed to persist error snapshot run_id=%s", run_id)
            raise
