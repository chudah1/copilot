import logging

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.portfolio_sync import run_portfolio_sync
from app.jobs.monitoring_run import run_monitoring
from app.jobs.digest_builder import run_digest_builder
from app.jobs.quarterly_review_prep import run_quarterly_review_prep
from app.jobs.earnings_refresh import run_earnings_refresh
from app.jobs.post_earnings_eval import run_post_earnings_evaluation
from app.jobs.onboarding_drip import run_onboarding_drip
from app.jobs.reengagement import run_reengagement
from app.jobs.signal_label_refresh import run_signal_label_refresh
from app.services.decision_resolution import run_decision_resolution

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


from datetime import datetime, timezone

# Last-run health per background job, surfaced via /health so a failed job is
# visible to monitoring instead of silently leaving the dashboard stale. We keep
# status + timestamp only here (no error strings — /health is public); the error
# detail goes to the logs and Sentry.
JOB_HEALTH: dict[str, dict] = {}


def _record_job_health(job_id: str, status: str) -> None:
    JOB_HEALTH[job_id] = {"status": status, "at": datetime.now(timezone.utc).isoformat()}


def _on_job_executed(event):
    logger.info("Job %s completed (retval=%s)", event.job_id, event.retval)
    _record_job_health(event.job_id, "ok")


def _on_job_error(event):
    logger.error("Job %s raised an exception: %s", event.job_id, event.exception, exc_info=event.traceback)
    _record_job_health(event.job_id, "error")
    try:  # best-effort alerting if Sentry is configured; never fail the listener
        import sentry_sdk

        sentry_sdk.capture_exception(event.exception)
    except Exception:
        pass


def _on_job_missed(event):
    logger.warning("Job %s missed its scheduled run time", event.job_id)
    _record_job_health(event.job_id, "missed")


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
    scheduler.add_job(run_post_earnings_evaluation, "cron", hour=8, minute=0, id="post_earnings_eval")
    scheduler.add_job(run_onboarding_drip, "cron", hour=9, minute=0, id="onboarding_drip")
    scheduler.add_job(run_reengagement, "cron", hour=10, minute=0, id="reengagement")
    scheduler.add_job(run_signal_label_refresh, "cron", day_of_week="sat", hour=5, minute=0, id="signal_label_refresh")
    # Decision-mirror resolution: read back conviction calls whose bet has been tested.
    scheduler.add_job(run_decision_resolution, "cron", hour=11, minute=0, id="decision_resolution")

    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
    scheduler.start()
    logger.info(
        "Scheduler started with 10 jobs: portfolio_sync, monitoring_run, digest_builder, "
        "quarterly_review_prep, earnings_refresh, post_earnings_eval, "
        "onboarding_drip, reengagement, signal_label_refresh, decision_resolution"
    )


def shutdown_scheduler():
    scheduler.shutdown()
