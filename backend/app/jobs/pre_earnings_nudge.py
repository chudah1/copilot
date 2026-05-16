"""Daily job: create in-app notifications for earnings within 2 days."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_

from app.database import async_session
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.models.user_notification import UserNotification

logger = logging.getLogger(__name__)

NUDGE_DAYS_AHEAD = 2


async def run_pre_earnings_nudge() -> None:
    logger.info("Running pre-earnings nudge job")
    now = datetime.now(timezone.utc)
    window_start = now
    window_end = now + timedelta(days=NUDGE_DAYS_AHEAD + 1)

    async with async_session() as db:
        # Find earnings within the nudge window
        earnings_result = await db.execute(
            select(EarningsCalendar).where(
                EarningsCalendar.report_date >= window_start,
                EarningsCalendar.report_date <= window_end,
            )
        )
        upcoming = earnings_result.scalars().all()

        if not upcoming:
            logger.info("No earnings within nudge window, skipping")
            return

        upcoming_tickers = {e.ticker: e.report_date for e in upcoming}

        # Find all users holding these tickers who have an active thesis
        holdings_result = await db.execute(
            select(Holding, Thesis)
            .join(Thesis, and_(
                Thesis.holding_id == Holding.id,
                Thesis.status.in_(["active", "needs_review", "draft"]),
            ))
            .where(Holding.ticker.in_(list(upcoming_tickers.keys())))
        )
        pairs = holdings_result.all()

        user_ids_needed = {holding.user_id for holding, _ in pairs}
        users_result = await db.execute(select(User).where(User.id.in_(user_ids_needed)))
        user_prefs: dict = {
            u.id: (u.preferences or {}) for u in users_result.scalars().all()
        }

        # Batch-load today's pre_earnings notifications to avoid N+1 dedup checks
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        holding_ids_in_pairs = [h.id for h, _ in pairs]
        existing_result = await db.execute(
            select(UserNotification.user_id, UserNotification.holding_id).where(
                UserNotification.holding_id.in_(holding_ids_in_pairs),
                UserNotification.notification_type == "pre_earnings",
                UserNotification.created_at >= today_start,
            )
        )
        already_nudged = {(row.user_id, row.holding_id) for row in existing_result.all()}

        nudges_created = 0
        for holding, thesis in pairs:
            report_date = upcoming_tickers.get(holding.ticker.upper())
            if report_date is None:
                continue

            prefs = user_prefs.get(holding.user_id, {})
            if not prefs.get("email_enabled", True):
                continue
            if not prefs.get("earnings_alerts", True):
                continue

            if (holding.user_id, holding.id) in already_nudged:
                continue

            # Build signal summary from thesis interpretation
            watch_hints = _extract_watch_hints(thesis.interpretation)
            signal_lines = "\n".join(f"- {h}" for h in watch_hints[:3]) if watch_hints else ""

            days_until = max(0, (report_date.date() - now.date()).days)
            date_str = report_date.strftime("%B %-d")

            content = (
                f"{holding.ticker} reports earnings in {days_until} day{'s' if days_until != 1 else ''} ({date_str})."
            )
            if signal_lines:
                content += f"\n\nYour key signals to watch:\n{signal_lines}"
            content += "\n\nWe'll evaluate against your reason the morning after."

            notification = UserNotification(
                user_id=holding.user_id,
                notification_type="pre_earnings",
                holding_id=holding.id,
                thesis_id=thesis.id,
                content=content,
                metadata_json={
                    "ticker": holding.ticker,
                    "report_date": report_date.isoformat(),
                    "days_until": days_until,
                },
            )
            db.add(notification)
            nudges_created += 1

        await db.commit()
        logger.info("Created %d pre-earnings nudges", nudges_created)


def _extract_watch_hints(interpretation: dict | None) -> list[str]:
    if not interpretation:
        return []
    watch_hints = interpretation.get("watch_hints", [])
    result = []
    for hint in watch_hints:
        if not isinstance(hint, dict):
            continue
        label = hint.get("label") or hint.get("metric") or hint.get("kind", "")
        if label:
            result.append(str(label))
    return result
