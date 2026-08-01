"""Daily job: run monitoring for tickers that reported earnings yesterday."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.database import async_session
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.user import User
from app.services.check_now import run_check_now
from app.services.email import send_earnings_alert_email
from app.config import settings

logger = logging.getLogger(__name__)


def event_requires_post_earnings_email(event: MonitoringEvent) -> bool:
    """Only adverse evidence should interrupt the user after earnings."""
    return (
        event.severity in {"warning", "thesis_breaking"}
        and event.verdict not in {"supports", "neutral"}
    )


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

        user_ids = {h.user_id for h, _ in pairs}
        users_map: dict = {}
        if user_ids:
            users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
            users_map = {u.id: u for u in users_result.scalars().all()}

        targets: list[dict] = []
        for holding, thesis in pairs:
            holding_user_id = holding.user_id
            user = users_map.get(holding_user_id)
            targets.append(
                {
                    "holding_id": holding.id,
                    "thesis_id": thesis.id,
                    "ticker": holding.ticker,
                    "company_name": holding.name,
                    "user_id": holding_user_id,
                    "email": user.email if user else None,
                    "preferences": dict(user.preferences or {}) if user else {},
                }
            )

    evaluated = 0
    for target in targets:
        ticker = target["ticker"]
        company_name = target["company_name"]
        holding_user_id = target["user_id"]
        user_email = target["email"]
        prefs = target["preferences"]
        try:
            # run_check_now deliberately rolls back its caller-owned session
            # before external work. Give every target a fresh session so that
            # rollback cannot expire the ORM objects for the next holding.
            async with async_session() as db:
                holding = (
                    await db.execute(
                        select(Holding).where(Holding.id == target["holding_id"])
                    )
                ).scalar_one_or_none()
                thesis = (
                    await db.execute(
                        select(Thesis).where(Thesis.id == target["thesis_id"])
                    )
                ).scalar_one_or_none()
                if holding is None or thesis is None:
                    continue

                # This job owns the single post-earnings email. Suppress the
                # normal immediate alert from check-now so one event cannot
                # produce two messages.
                result = await run_check_now(holding, thesis, db, send_alerts=False)
                adverse_events: list[MonitoringEvent] = []
                if result.created_event_ids:
                    created_rows = await db.execute(
                        select(MonitoringEvent).where(
                            MonitoringEvent.id.in_(result.created_event_ids)
                        )
                    )
                    adverse_events = [
                        event
                        for event in created_rows.scalars().all()
                        if event_requires_post_earnings_email(event)
                    ]
            if adverse_events:
                adverse_count = len(adverse_events)
                logger.info(
                    "Post-earnings: %d events for %s (user %s)",
                    adverse_count,
                    ticker,
                    holding_user_id,
                )
                if user_email and prefs.get("email_enabled", True) and prefs.get("earnings_alerts", True):
                    subject = f"{ticker} reported — {adverse_count} signal{'s' if adverse_count != 1 else ''} affected your reason"
                    html = _build_post_earnings_email(ticker, company_name, adverse_count)
                    await send_earnings_alert_email(user_email, subject, html)
            evaluated += 1
        except Exception as exc:
            logger.error(
                "Post-earnings eval failed for %s / user %s: %s",
                ticker,
                holding_user_id,
                exc,
                exc_info=True,
            )

    logger.info("Post-earnings evaluation complete: %d holdings evaluated", evaluated)


def _build_post_earnings_email(ticker: str, name: str | None, events_created: int) -> str:
    company = name or ticker
    position_url = f"{settings.frontend_url}/dashboard/positions/{ticker}"
    signal_word = f"{events_created} signal{'s' if events_created != 1 else ''}"
    return f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;background:#faf8f5;padding:40px 32px;">
      <p style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#8b7355;font-family:monospace;margin:0 0 28px;">penKeep &middot; Post-Earnings Review</p>
      <h1 style="font-size:26px;font-weight:400;color:#2d1f0e;margin:0 0 16px;font-style:italic;line-height:1.3;">{ticker} reported — {signal_word} touched your reason</h1>
      <p style="color:#5c4a2a;font-size:15px;line-height:1.7;margin:0 0 24px;">{company} has reported earnings. We evaluated the results against your reason and found {signal_word} worth reviewing.</p>
      <a href="{position_url}" style="display:inline-block;font-family:monospace;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#8b4513;text-decoration:none;border:1px solid #8b4513;padding:10px 20px;">Review what changed &rarr;</a>
      <p style="margin:40px 0 0;font-size:11px;color:#b8a89a;font-family:monospace;">You're receiving this because earnings alerts are enabled. <a href="{settings.frontend_url}/settings" style="color:#8b7355;">Manage preferences</a></p>
    </div>"""
