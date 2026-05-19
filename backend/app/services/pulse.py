import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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
    pnl_pct: float | None = None
    last_checked_at: datetime | None = None
    recent_event_count: int = 0


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _next_sunday_8am() -> datetime:
    now = datetime.now(timezone.utc)
    days_ahead = 6 - now.weekday()  # Sunday = 6
    if days_ahead < 0 or (days_ahead == 0 and now.hour >= 8):
        days_ahead += 7
    next_sunday = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    return next_sunday


def _days_since_update(updated_at: datetime | None, *, now: datetime) -> int | None:
    normalized = _normalize_datetime(updated_at)
    if normalized is None:
        return None
    return (now - normalized).days


def _compute_pnl_pct(holding: Holding) -> float | None:
    quantity = _to_float(holding.quantity)
    average_cost_basis = _to_float(holding.average_cost_basis)
    if quantity is None or average_cost_basis is None:
        return None

    cost = quantity * average_cost_basis
    if cost <= 0:
        return None

    current_value = _to_float(holding.current_value)
    value = current_value if current_value is not None else cost
    return round((value - cost) / cost * 100, 2)


def _combined_event_summary(events: list[MonitoringEvent], *, now: datetime) -> str | None:
    if not events:
        return None
    if len(events) == 1:
        return events[0].summary

    today_events = [event for event in events if event.created_at.date() == now.date()]
    if len(today_events) < 2:
        return events[0].summary

    labels: list[str] = []
    for event in today_events:
        label = getattr(event, "signal_label", None) or event.evidence_type or event.event_type
        label = str(label).replace("_", " ").strip()
        if label and label not in labels:
            labels.append(label)

    if not labels:
        return events[0].summary

    preview = ", ".join(labels[:3])
    if len(labels) > 3:
        preview += ", and more"
    return f"{len(today_events)} new signals today: {preview}."


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

    # Load most recent event per holding (any time, not just last 7 days) for "last checked"
    last_event_result = await db.execute(
        select(MonitoringEvent.holding_id, func.max(MonitoringEvent.created_at).label("last_at"))
        .where(MonitoringEvent.holding_id.in_(holding_ids))
        .group_by(MonitoringEvent.holding_id)
    )
    last_checked_map: dict[uuid.UUID, datetime] = {
        row[0]: _normalize_datetime(row[1])
        for row in last_event_result.fetchall()
    }

    for holding in holdings:
        thesis = thesis_by_holding.get(holding.id)
        events = events_by_holding.get(holding.id, [])

        # P&L percent
        pnl_pct = _compute_pnl_pct(holding)

        last_checked = last_checked_map.get(holding.id)

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
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))
            continue

        days_since_update = _days_since_update(thesis.updated_at, now=now)
        latest_summary = _combined_event_summary(events, now=now)

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
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))
        elif "warning" in severities or (days_since_update is not None and days_since_update > 60):
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
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
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
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))

    return pulses, _next_sunday_8am()
