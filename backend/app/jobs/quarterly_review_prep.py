import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.quarterly_review import QuarterlyReview
from app.models.user import User
from app.services.email import send_onboarding_email
from app.services.quarterly_review import (
    build_current_review_snapshot,
    current_quarter_key,
    get_or_create_current_review,
    is_quarterly_review_open,
)

logger = logging.getLogger(__name__)


def _quarterly_nudge_html(quarter: str, pending_count: int, first_ticker: str | None) -> str:
    holding_text = f"{first_ticker} and {pending_count - 1} other{'s' if pending_count - 1 != 1 else ''}" if first_ticker and pending_count > 1 else (first_ticker or f"{pending_count} holdings")
    return (
        f"<h2>Quarterly Conviction Review — {quarter}</h2>"
        "<p>Once a quarter, we ask one simple question about each of your positions:</p>"
        "<blockquote><em>Knowing what you know now, would you buy this today at this price for the same reason?</em></blockquote>"
        f"<p>You have <strong>{pending_count} holding{'s' if pending_count != 1 else ''}</strong> to revisit this quarter, starting with {holding_text}.</p>"
        "<p>This takes about 2 minutes per holding. The answers go into your conviction log.</p>"
        '<p><a href="/dashboard/quarterly-review">→ Start quarterly review</a></p>'
    )


async def run_quarterly_review_prep(
    *,
    now: datetime | None = None,
    session_factory=async_session,
) -> None:
    reference = now or datetime.now(timezone.utc)
    if not is_quarterly_review_open(reference):
        logger.info("Quarterly review prep skipped: release window not open yet")
        return

    quarter = current_quarter_key(reference)

    async with session_factory() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()
        created_count = 0
        nudge_count = 0

        for user in users:
            try:
                # Check if review already exists for this quarter
                existing_result = await db.execute(
                    select(QuarterlyReview).where(
                        QuarterlyReview.user_id == user.id,
                        QuarterlyReview.quarter == quarter,
                    )
                )
                is_new = existing_result.scalar_one_or_none() is None

                review = await get_or_create_current_review(db, user_id=user.id, now=reference)
                if is_new:
                    created_count += 1

                # Send nudge email for newly created reviews
                prefs = user.preferences or {}
                if (
                    is_new
                    and prefs.get("email_enabled", True)
                    and prefs.get("quarterly_review_reminders", True)
                ):
                    _, items = await build_current_review_snapshot(db, user_id=user.id, now=reference)
                    pending = [item for item in items if item.response is None]
                    if pending:
                        first_ticker = pending[0].ticker
                        subject = f"Quarterly Conviction Review — {quarter} ({len(pending)} holding{'s' if len(pending) != 1 else ''})"
                        html = _quarterly_nudge_html(quarter, len(pending), first_ticker)
                        sent = await send_onboarding_email(user.email, subject, html)
                        if sent:
                            nudge_count += 1

            except Exception as exc:
                logger.error("Quarterly review prep failed for user %s: %s", user.id, exc)
                continue

        await db.commit()
        logger.info(
            "Quarterly review prep complete: %d reviews created, %d nudge emails sent",
            created_count,
            nudge_count,
        )
