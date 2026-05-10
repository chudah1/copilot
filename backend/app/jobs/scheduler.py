import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.portfolio_sync import run_portfolio_sync
from app.jobs.monitoring_run import run_monitoring
from app.jobs.digest_builder import run_digest_builder

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler():
    scheduler.add_job(run_portfolio_sync, "interval", hours=4, id="portfolio_sync")
    scheduler.add_job(run_monitoring, "cron", hour=6, minute=0, id="monitoring_run")
    scheduler.add_job(run_digest_builder, "cron", day_of_week="sun", hour=18, minute=0, id="digest_builder")

    scheduler.start()
    logger.info("Scheduler started with 3 jobs: portfolio_sync, monitoring_run, digest_builder")


def shutdown_scheduler():
    scheduler.shutdown()
