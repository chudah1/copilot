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


def _age_in_days(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - normalized).days


def _digest_headline(events_count: int, stale_count: int, missing_count: int, stable_count: int) -> str:
    if events_count > 0:
        verb = "needs" if events_count == 1 else "need"
        return f"{events_count} thesis event{'s' if events_count != 1 else ''} {verb} your attention."
    if stale_count > 0:
        return f"{stale_count} thesis{'es' if stale_count != 1 else ''} went stale this week."
    if missing_count > 0:
        return f"{missing_count} holding{'s' if missing_count != 1 else ''} still lack a thesis."
    if stable_count > 0:
        return "Your monitored holdings stayed stable this week."
    return "No material portfolio changes this week."


def _digest_summary_points(events_data: list[dict], observations: dict) -> list[str]:
    points: list[str] = []
    if events_data:
        first = events_data[0]
        points.append(f"{first['ticker']}: {first['summary']}")
    if observations.get("stale_theses"):
        points.append(f"Stale theses: {', '.join(observations['stale_theses'][:3])}")
    if observations.get("missing_theses"):
        points.append(f"Missing theses: {', '.join(observations['missing_theses'][:3])}")
    if observations.get("concentration_warnings"):
        points.append(f"Concentration: {observations['concentration_warnings']}")
    stable = observations.get("stable_holdings", [])
    if stable and not points:
        points.append(f"Stable holdings: {', '.join(item['ticker'] for item in stable[:3])}")
    return points[:3]


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
                stable_holdings = []

                for h in holdings:
                    theses_result = await db.execute(
                        select(Thesis)
                        .where(Thesis.holding_id == h.id, Thesis.status.in_(["draft", "active", "needs_review"]))
                        .order_by(Thesis.created_at.desc())
                        .limit(1)
                    )
                    thesis = theses_result.scalar_one_or_none()

                    entry = {"ticker": h.ticker, "name": h.name, "holding_id": str(h.id)}
                    if thesis:
                        entry["why_own_it"] = thesis.why_own_it
                        entry["must_remain_true"] = thesis.must_remain_true
                        entry["what_would_change_my_mind"] = thesis.what_would_change_my_mind
                        entry["ai_summary"] = thesis.ai_summary
                        entry["thesis_status"] = thesis.status
                        if _age_in_days(thesis.updated_at) > 90:
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
                event_holding_ids = set()
                for e in events:
                    holding = next((h for h in holdings if h.id == e.holding_id), None)
                    event_holding_ids.add(e.holding_id)
                    events_data.append({
                        "ticker": holding.ticker if holding else "Unknown",
                        "severity": e.severity,
                        "title": e.title,
                        "summary": e.summary,
                        "ai_analysis": e.ai_analysis,
                    })

                for entry in holdings_with_theses:
                    holding_id = entry["holding_id"]
                    if holding_id in {str(hid) for hid in event_holding_ids}:
                        continue
                    if entry.get("why_own_it"):
                        stable_holdings.append(
                            {
                                "ticker": entry["ticker"],
                                "name": entry["name"],
                                "thesis_status": entry.get("thesis_status", "draft"),
                                "stale": entry["ticker"] in stale_theses,
                            }
                        )

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
                    "stable_holdings": stable_holdings,
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
                        "stable_holdings_count": len(stable_holdings),
                        "headline": _digest_headline(
                            len(events_data),
                            len(stale_theses),
                            len(missing_theses),
                            len(stable_holdings),
                        ),
                        "summary_points": _digest_summary_points(events_data, observations),
                        "missing_theses_count": len(missing_theses),
                        "stale_theses_count": len(stale_theses),
                        "concentration_warning": concentration_warnings,
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
