import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.digest import Digest
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.user import User
from app.services.ai_digest import generate_digest_content
from app.services.email import send_digest_email

logger = logging.getLogger(__name__)


async def run_digest_builder():
    logger.info("Starting weekly digest builder")

    now = datetime.now(timezone.utc)
    period_end = now
    period_start = now - timedelta(days=7)

    async with async_session() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        for user in users:
            try:
                frequency = user.preferences.get("digest_frequency", "weekly")
                if frequency == "none":
                    continue

                holdings_result = await db.execute(
                    select(Holding).where(Holding.user_id == user.id)
                )
                holdings = holdings_result.scalars().all()
                if not holdings:
                    continue

                holdings_with_theses = []
                missing_theses = []
                stale_theses = []

                for h in holdings:
                    theses_result = await db.execute(
                        select(Thesis)
                        .where(Thesis.holding_id == h.id, Thesis.status.in_(["active", "needs_review"]))
                        .order_by(Thesis.created_at.desc())
                        .limit(1)
                    )
                    thesis = theses_result.scalar_one_or_none()

                    entry = {"ticker": h.ticker, "name": h.name, "holding_id": str(h.id)}
                    if thesis:
                        entry["bull_case"] = thesis.bull_case
                        entry["thesis_status"] = thesis.status
                        if (now - thesis.updated_at).days > 90:
                            stale_theses.append(h.ticker)
                    else:
                        missing_theses.append(h.ticker)

                    holdings_with_theses.append(entry)

                events_result = await db.execute(
                    select(MonitoringEvent)
                    .join(Holding)
                    .where(
                        Holding.user_id == user.id,
                        MonitoringEvent.created_at >= period_start,
                        MonitoringEvent.created_at <= period_end,
                    )
                    .order_by(MonitoringEvent.created_at.desc())
                )
                events = events_result.scalars().all()

                events_data = []
                for e in events:
                    holding = next((h for h in holdings if h.id == e.holding_id), None)
                    events_data.append({
                        "ticker": holding.ticker if holding else "Unknown",
                        "severity": e.severity,
                        "title": e.title,
                        "summary": e.summary,
                    })

                total_value = sum(float(h.current_value or 0) for h in holdings)
                concentration_warnings = ""
                if total_value > 0:
                    sector_pcts = {}
                    for h in holdings:
                        s = h.sector or "Unknown"
                        sector_pcts[s] = sector_pcts.get(s, 0) + float(h.current_value or 0) / total_value * 100
                    high_conc = {k: round(v, 1) for k, v in sector_pcts.items() if v > 30}
                    if high_conc:
                        concentration_warnings = ", ".join(f"{k}: {v}%" for k, v in high_conc.items())

                observations = {
                    "concentration_warnings": concentration_warnings,
                    "stale_theses": stale_theses,
                    "missing_theses": missing_theses,
                }

                html_content = await generate_digest_content(holdings_with_theses, events_data, observations)

                digest = Digest(
                    user_id=user.id,
                    period_start=period_start,
                    period_end=period_end,
                    content={
                        "html": html_content or "<p>Unable to generate digest this week.</p>",
                        "events_count": len(events_data),
                        "holdings_count": len(holdings),
                    },
                    status="pending",
                )
                db.add(digest)
                await db.flush()

                for e in events:
                    e.included_in_digest_id = digest.id

                if html_content:
                    week_str = period_end.strftime("%d %b %Y")
                    sent = await send_digest_email(
                        to_email=user.email,
                        subject=f"Your Weekly Investment Digest — {week_str}",
                        html_content=html_content,
                    )
                    digest.status = "sent" if sent else "failed"
                    digest.sent_at = datetime.now(timezone.utc) if sent else None
                else:
                    digest.status = "failed"

                await db.commit()
                logger.info(f"Digest {'sent' if digest.status == 'sent' else 'failed'} for user {user.id}")

            except Exception as e:
                logger.error(f"Digest build failed for user {user.id}: {e}")
                continue

    logger.info("Weekly digest builder complete")
