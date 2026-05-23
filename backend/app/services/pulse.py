import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_signal import ThesisSignal


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
    assumption_label: str | None = None
    latest_event_at: datetime | None = None
    urgency_score: int = 0
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


def _monitorability(thesis: Thesis) -> str | None:
    interpretation = thesis.interpretation or {}
    value = interpretation.get("monitorability")
    return value if isinstance(value, str) else None


def _stale_pressure(thesis: Thesis, *, days_since_update: int | None) -> tuple[str | None, str | None]:
    if days_since_update is None:
        return None, None

    cadence_days = max(thesis.review_cadence_days or 30, 14)
    monitorability = _monitorability(thesis)

    watch_threshold = max(cadence_days, 21)
    review_threshold = max(cadence_days * 3, 120)

    if thesis.confidence == "high":
        watch_threshold = max(watch_threshold - 7, 21)
        review_threshold = max(review_threshold - 14, 90)

    if monitorability == "low":
        watch_threshold = max(watch_threshold - 7, 14)
        review_threshold = max(review_threshold - 14, 75)

    if days_since_update >= review_threshold:
        return (
            "review",
            f"This thesis is {days_since_update} days old and far past its {cadence_days}-day review cadence.",
        )

    if days_since_update >= watch_threshold:
        overdue_days = max(days_since_update - cadence_days, 0)
        overdue_text = (
            f" and {overdue_days} days past its review cadence"
            if overdue_days > 0
            else ""
        )
        return (
            "watch",
            f"This thesis is {days_since_update} days old{overdue_text}.",
        )

    return None, None


def _urgency_score(*, pulse_status: str, recent_event_count: int, latest_event_at: datetime | None, days_since_update: int | None) -> int:
    score = {
        "review": 90,
        "watch": 55,
        "intact": 10,
    }.get(pulse_status, 0)

    if recent_event_count > 0:
        score += min(recent_event_count * 4, 12)

    normalized_event_at = _normalize_datetime(latest_event_at)
    if normalized_event_at is not None:
        event_age_days = max((datetime.now(timezone.utc) - normalized_event_at).days, 0)
        score += max(10 - min(event_age_days, 10), 0)

    if days_since_update is not None and days_since_update > 30:
        score += min((days_since_update - 30) // 15 + 1, 8)

    return score


def _normalize_assumption_label(label: str | None, *, ticker: str | None = None) -> str | None:
    if not isinstance(label, str):
        return None

    cleaned = " ".join(label.strip().split())
    if not cleaned:
        return None

    cleaned = re.sub(r"^(?:[A-Z0-9_.-]+:)+", "", cleaned).strip()

    lower_cleaned = cleaned.lower()
    for marker in ("news touches", "earnings touch", "event touches"):
        if lower_cleaned.startswith(marker):
            cleaned = cleaned[len(marker):].strip(" :'-\"")
            break

    if ticker:
        ticker_upper = ticker.strip().upper()
        if ticker_upper:
            cleaned = re.sub(
                rf"^(?:{re.escape(ticker_upper)}[\s:._-]+)+",
                "",
                cleaned,
                flags=re.IGNORECASE,
            ).strip()

    cleaned = cleaned.strip(" '\"")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(".,;:-")

    return cleaned or None


def _event_assumption_label(
    event: MonitoringEvent,
    *,
    signal_labels: dict[uuid.UUID, str],
    ticker: str | None = None,
) -> str | None:
    if event.signal_id and event.signal_id in signal_labels:
        label = signal_labels[event.signal_id]
        normalized = _normalize_assumption_label(label, ticker=ticker)
        if normalized:
            return normalized

    raw_data = event.raw_data or {}
    if isinstance(raw_data, dict):
        raw_label = raw_data.get("signal_label")
        normalized = _normalize_assumption_label(raw_label, ticker=ticker)
        if normalized:
            return normalized

    normalized_title = _normalize_assumption_label(event.title, ticker=ticker)
    if normalized_title:
        return normalized_title

    return None


def _event_decision_summary(event: MonitoringEvent) -> str:
    for candidate in (event.ai_analysis, event.evidence_summary, event.summary):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return event.title.strip()


def _combined_event_summary(
    events: list[MonitoringEvent],
    *,
    now: datetime,
    signal_labels: dict[uuid.UUID, str],
    ticker: str | None = None,
) -> str | None:
    if not events:
        return None
    if len(events) == 1:
        return _event_decision_summary(events[0])

    recent_cutoff = now - timedelta(hours=24)
    recent_batch = [
        e for e in events
        if e.created_at is not None and _normalize_datetime(e.created_at) >= recent_cutoff
    ]
    if len(recent_batch) < 2:
        return _event_decision_summary(events[0])

    labels: list[str] = []
    for event in recent_batch:
        label = (
            _event_assumption_label(event, signal_labels=signal_labels, ticker=ticker)
            or event.evidence_type
            or event.event_type
        )
        label = str(label).replace("_", " ").strip()
        if label and label not in labels:
            labels.append(label)

    if not labels:
        return events[0].summary

    preview = ", ".join(labels[:3])
    if len(labels) > 3:
        preview += ", and more"
    return f"{len(recent_batch)} new signals today: {preview}."


async def compute_portfolio_pulse(user_id: uuid.UUID, db: AsyncSession) -> tuple[list[HoldingPulse], datetime]:
    """Compute pulse status for all holdings. Returns (pulses, next_digest_at)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Load holdings
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )
    holdings = list(holdings_result.scalars().all())

    if not holdings:
        return [], _next_sunday_8am(), []

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

    signal_ids = [event.signal_id for event in all_events if event.signal_id]
    signal_labels: dict[uuid.UUID, str] = {}
    if signal_ids:
        signals_result = await db.execute(
            select(ThesisSignal.id, ThesisSignal.signal_label).where(ThesisSignal.id.in_(signal_ids))
        )
        signal_labels = {
            signal_id: signal_label
            for signal_id, signal_label in signals_result.all()
            if isinstance(signal_label, str) and signal_label.strip()
        }

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
        latest_event_at = _normalize_datetime(events[0].created_at) if events else None

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
                latest_event_at=latest_event_at,
                urgency_score=100,
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))
            continue

        days_since_update = _days_since_update(thesis.updated_at, now=now)
        latest_summary = _combined_event_summary(events, now=now, signal_labels=signal_labels)
        latest_assumption = (
            _event_assumption_label(events[0], signal_labels=signal_labels)
            if events
            else None
        )
        stale_status, stale_reason = _stale_pressure(thesis, days_since_update=days_since_update)

        # Determine pulse
        severities = {e.severity for e in events}
        if thesis.status == "needs_review" or "thesis_breaking" in severities:
            pulse_status = "review"
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                reason=latest_summary or (
                    f"{latest_assumption} needs a decision."
                    if latest_assumption
                    else "Thesis needs review — something changed that matters."
                ),
                assumption_label=latest_assumption,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
                latest_event_at=latest_event_at,
                urgency_score=_urgency_score(
                    pulse_status=pulse_status,
                    recent_event_count=len(events),
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))
        elif "warning" in severities or stale_status in {"watch", "review"}:
            pulse_status = stale_status or "watch"
            reason = latest_summary or stale_reason or f"Thesis is {days_since_update} days old — consider reviewing."
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                reason=reason,
                assumption_label=latest_assumption,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
                latest_event_at=latest_event_at,
                urgency_score=_urgency_score(
                    pulse_status=pulse_status,
                    recent_event_count=len(events),
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))
        else:
            pulse_status = "intact"
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                reason="Nothing meaningful changed — your assumptions still hold.",
                assumption_label=latest_assumption,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
                latest_event_at=latest_event_at,
                urgency_score=_urgency_score(
                    pulse_status=pulse_status,
                    recent_event_count=len(events),
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=len(events),
            ))

    ticker_by_holding = {h.id: h.ticker for h in holdings}
    top_events = sorted(all_events, key=lambda e: e.created_at or datetime.min, reverse=True)[:5]
    recent_events = [
        {
            "holding_id": e.holding_id,
            "ticker": ticker_by_holding.get(e.holding_id, ""),
            "title": e.title or e.summary or "",
            "severity": e.severity,
            "event_type": e.event_type,
            "created_at": _normalize_datetime(e.created_at),
        }
        for e in top_events
        if e.severity in {"info", "warning", "thesis_breaking"}
    ]
    return pulses, _next_sunday_8am(), recent_events
