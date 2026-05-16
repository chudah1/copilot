import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.portfolio_sync import run_portfolio_sync
from app.jobs.monitoring_run import run_monitoring
from app.jobs.digest_builder import run_digest_builder
from app.jobs.quarterly_review_prep import run_quarterly_review_prep
from app.jobs.earnings_refresh import run_earnings_refresh
from app.jobs.pre_earnings_nudge import run_pre_earnings_nudge
from app.jobs.post_earnings_eval import run_post_earnings_evaluation

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler():
    scheduler.add_job(run_portfolio_sync, "interval", hours=4, id="portfolio_sync")
    scheduler.add_job(run_monitoring, "cron", hour=6, minute=0, id="monitoring_run")
    scheduler.add_job(run_digest_builder, "cron", day_of_week="sun", hour=18, minute=0, id="digest_builder")
    scheduler.add_job(
        run_quarterly_review_prep,
        "cron",
        month="1,4,7,10",
        day="1-7",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="quarterly_review_prep",
    )
    # Earnings pipeline jobs
    scheduler.add_job(run_earnings_refresh, "cron", day_of_week="mon", hour=7, minute=0, id="earnings_refresh")
    scheduler.add_job(run_pre_earnings_nudge, "cron", hour=7, minute=30, id="pre_earnings_nudge")
    scheduler.add_job(run_post_earnings_evaluation, "cron", hour=8, minute=0, id="post_earnings_eval")

    scheduler.start()
    logger.info(
        "Scheduler started with 7 jobs: portfolio_sync, monitoring_run, digest_builder, "
        "quarterly_review_prep, earnings_refresh, pre_earnings_nudge, post_earnings_eval"
    )


def shutdown_scheduler():
    scheduler.shutdown()
