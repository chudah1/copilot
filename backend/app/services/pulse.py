import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis


@dataclass
class HoldingPulse:
    holding_id: uuid.UUID
    ticker: str
    name: str
    pulse_status: str  # intact | watch | review
    reason: str
    latest_event_summary: str | None
    days_since_thesis_update: int | None
    has_thesis: bool


def _next_sunday_8am() -> datetime:
    now = datetime.now(timezone.utc)
    days_ahead = 6 - now.weekday()  # Sunday = 6
    if days_ahead < 0 or (days_ahead == 0 and now.hour >= 8):
        days_ahead += 7
    next_sunday = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_sunday


async def compute_portfolio_pulse(user_id: uuid.UUID, db: AsyncSession) -> tuple[list[HoldingPulse], datetime]:
    """Compute pulse status for all holdings. Returns (pulses, next_digest_at)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Load holdings
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )
    holdings = list(holdings_result.scalars().all())

    if not holdings:
        return [], _next_sunday_8am()

    holding_ids = [h.id for h in holdings]

    # Load latest thesis per holding (active/draft/needs_review)
    theses_result = await db.execute(
        select(Thesis).where(
            Thesis.user_id == user_id,
            Thesis.holding_id.in_(holding_ids),
            Thesis.status.in_(["active", "draft", "needs_review"]),
        ).order_by(Thesis.created_at.desc())
    )
    all_theses = list(theses_result.scalars().all())
    thesis_by_holding: dict[uuid.UUID, Thesis] = {}
    for t in all_theses:
        thesis_by_holding.setdefault(t.holding_id, t)

    # Load recent events per holding (last 7 days)
    events_result = await db.execute(
        select(MonitoringEvent).where(
            MonitoringEvent.holding_id.in_(holding_ids),
            MonitoringEvent.created_at >= cutoff,
        ).order_by(MonitoringEvent.created_at.desc())
    )
    all_events = list(events_result.scalars().all())
    events_by_holding: dict[uuid.UUID, list[MonitoringEvent]] = {}
    for e in all_events:
        events_by_holding.setdefault(e.holding_id, []).append(e)

    pulses: list[HoldingPulse] = []
    now = datetime.now(timezone.utc)

    for holding in holdings:
        thesis = thesis_by_holding.get(holding.id)
        events = events_by_holding.get(holding.id, [])

        if not thesis:
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status="review",
                reason="No thesis — this position has no documented reason to exist.",
                latest_event_summary=None,
                days_since_thesis_update=None,
                has_thesis=False,
            ))
            continue

        if thesis.updated_at:
            updated = thesis.updated_at if thesis.updated_at.tzinfo is not None else thesis.updated_at.replace(tzinfo=timezone.utc)
            days_since_update = (now - updated).days
        else:
            days_since_update = None
        latest_event = events[0] if events else None
        latest_summary = latest_event.summary if latest_event else None

        # Determine pulse
        severities = {e.severity for e in events}
        if thesis.status == "needs_review" or "thesis_breaking" in severities:
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status="review",
                reason=latest_summary or "Thesis needs review — something changed that matters.",
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
            ))
        elif "warning" in severities or (days_since_update and days_since_update > 60):
            reason = latest_summary or f"Thesis is {days_since_update} days old — consider reviewing."
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status="watch",
                reason=reason,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
            ))
        else:
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status="intact",
                reason="No material changes — thesis conditions holding.",
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
            ))

    return pulses, _next_sunday_8am()
