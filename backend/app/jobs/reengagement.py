"""Daily job: send ONE re-engagement email to users who've been inactive for 14+ days.

Inactive = hasn't logged in (last_seen_at) for 14+ days.
Sent at most once per user, ever. References a specific recent holding event so it
doesn't feel generic.
"""
import logging
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import and_, or_, select

from app.config import settings
from app.database import async_session
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.onboarding_state import OnboardingState
from app.models.user import User
from app.services.email import send_onboarding_email

logger = logging.getLogger(__name__)

INACTIVE_DAYS = 14


async def run_reengagement() -> None:
    logger.info("Running re-engagement job")
    now = datetime.now(timezone.utc)
    inactive_cutoff = now - timedelta(days=INACTIVE_DAYS)

    async with async_session() as db:
        # Pre-filter in SQL: email enabled, inactive 14+ days, reengagement not yet sent
        rows = await db.execute(
            select(User, OnboardingState)
            .join(OnboardingState, OnboardingState.user_id == User.id)
            .where(
                User.email.isnot(None),
                OnboardingState.reengagement_email_sent_at.is_(None),
                or_(
                    and_(User.last_seen_at.isnot(None), User.last_seen_at < inactive_cutoff),
                    and_(User.last_seen_at.is_(None), User.created_at < inactive_cutoff),
                ),
            )
        )
        candidates = rows.all()

        if not candidates:
            logger.info("No inactive users to re-engage")
            return

        sent_count = 0
        for user, state in candidates:
            try:
                if not (user.preferences or {}).get("email_enabled", True):
                    continue

                # Find the most recent monitoring event for this user
                event_result = await db.execute(
                    select(MonitoringEvent, Holding)
                    .join(Holding, MonitoringEvent.holding_id == Holding.id)
                    .where(
                        Holding.user_id == user.id,
                        MonitoringEvent.event_type != "monitoring_inactive",
                    )
                    .order_by(MonitoringEvent.created_at.desc())
                    .limit(1)
                )
                row = event_result.one_or_none()
                if row is None:
                    continue

                event, holding = row
                subject = f"Something changed for {holding.ticker} while you were away"
                html = _build_reengagement_html(holding.ticker, holding.name, event)
                ok = await send_onboarding_email(user.email, subject, html)
                if ok:
                    state.reengagement_email_sent_at = now
                    sent_count += 1
                    logger.info("Re-engagement email sent to user %s", user.id)

            except Exception:
                logger.exception("Re-engagement job failed for user %s", user.id)
                continue

        if sent_count:
            await db.commit()

    logger.info("Re-engagement job complete — sent %d emails", sent_count)


def _build_reengagement_html(ticker: str, name: str | None, event: MonitoringEvent) -> str:
    company = escape(name or ticker)
    ticker_escaped = escape(ticker)
    position_url = f"{settings.frontend_url}/dashboard/positions/{ticker}"
    what_happened = escape(event.evidence_summary or event.description or f"Something changed for {ticker}.")

    return f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:0 auto;background:#faf8f5;padding:40px 32px;">
      <p style="font-size:11px;letter-spacing:0.15em;text-transform:uppercase;color:#8b7355;margin:0 0 24px;">
        Copilot Investor
      </p>
      <h2 style="font-size:22px;font-weight:normal;color:#2c1810;margin:0 0 16px;font-style:italic;">
        Something moved on {ticker_escaped}
      </h2>
      <p style="font-size:15px;line-height:1.7;color:#5c4a2a;margin:0 0 16px;">
        You haven&apos;t logged in for a bit. This showed up on {company}:
      </p>
      <div style="background:#f0ebe3;border-left:3px solid #8b7355;padding:16px 20px;margin:0 0 24px;">
        <p style="margin:0;font-size:14px;line-height:1.6;color:#2c1810;">{what_happened}</p>
      </div>
      <p style="font-size:15px;line-height:1.7;color:#5c4a2a;margin:0 0 24px;">
        Worth checking whether your reason for holding still holds.
      </p>
      <a href="{position_url}" style="display:inline-block;background:#2c1810;color:#faf8f5;text-decoration:none;
         padding:12px 24px;font-size:13px;letter-spacing:0.1em;text-transform:uppercase;">
        Review {ticker_escaped} →
      </a>
      <p style="margin:32px 0 0;font-size:11px;color:#8b7355;">
        You're receiving this because you haven't logged in for a while.
        We won't send another email like this.
      </p>
    </div>
    """
