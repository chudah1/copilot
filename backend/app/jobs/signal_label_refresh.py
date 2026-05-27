import logging

from app.services.signal_label_refresh import refresh_stale_signal_labels

logger = logging.getLogger(__name__)


async def run_signal_label_refresh() -> None:
    logger.info("Starting signal label refresh job")
    try:
        await refresh_stale_signal_labels()
    except Exception as exc:
        logger.exception("Signal label refresh job failed: %s", exc)
