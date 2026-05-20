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
from app.services.email import send_earnings_alert_email
from app.config import settings

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

        upcoming_tickers = {e.ticker.upper(): e.report_date for e in upcoming}

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
        users_list = users_result.scalars().all()
        user_prefs: dict = {u.id: (u.preferences or {}) for u in users_list}
        users_map: dict = {u.id: u for u in users_list}

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

            # Send email alert
            user = users_map.get(holding.user_id)
            if user and user.email:
                subject = f"{holding.ticker} reports in {days_until} day{'s' if days_until != 1 else ''} — here's what matters for your reason"
                html = _build_pre_earnings_email(holding.ticker, holding.name, days_until, date_str, watch_hints[:3])
                await send_earnings_alert_email(user.email, subject, html)

            nudges_created += 1

        await db.commit()
        logger.info("Created %d pre-earnings nudges", nudges_created)


def _build_pre_earnings_email(ticker: str, name: str | None, days_until: int, date_str: str, signals: list[str]) -> str:
    company = name or ticker
    days_label = f"{days_until} day{'s' if days_until != 1 else ''}"
    signals_html = ""
    if signals:
        items = "".join(f'<li style="margin:4px 0;color:#5c4a2a;">{s}</li>' for s in signals)
        signals_html = f"""
        <p style="margin:24px 0 8px;font-size:13px;letter-spacing:0.1em;text-transform:uppercase;color:#8b7355;font-family:monospace;">Your key signals to watch</p>
        <ul style="margin:0;padding:0 0 0 20px;line-height:1.8;">{items}</ul>"""
    position_url = f"{settings.frontend_url}/dashboard/positions/{ticker}"
    return f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;background:#faf8f5;padding:40px 32px;">
      <p style="font-size:11px;letter-spacing:0.2em;text-transform:uppercase;color:#8b7355;font-family:monospace;margin:0 0 28px;">Copilot Investor &middot; Earnings Alert</p>
      <h1 style="font-size:26px;font-weight:400;color:#2d1f0e;margin:0 0 16px;font-style:italic;line-height:1.3;">{ticker} reports in {days_label}</h1>
      <p style="color:#5c4a2a;font-size:15px;line-height:1.7;margin:0 0 8px;">{company} is scheduled to report on <strong>{date_str}</strong>.</p>
      {signals_html}
      <p style="color:#5c4a2a;font-size:14px;line-height:1.6;margin:24px 0;padding:16px 20px;background:#f0ebe3;border-left:3px solid #8b4513;">
        We'll run a full evaluation the morning after and flag anything that touches your reason.
      </p>
      <a href="{position_url}" style="display:inline-block;font-family:monospace;font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#8b4513;text-decoration:none;border-bottom:1px solid #8b4513;padding-bottom:2px;">Review your reason &rarr;</a>
      <p style="margin:40px 0 0;font-size:11px;color:#b8a89a;font-family:monospace;">You're receiving this because earnings alerts are enabled. <a href="{settings.frontend_url}/settings" style="color:#8b7355;">Manage preferences</a></p>
    </div>"""


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
