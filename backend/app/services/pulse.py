import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage_pass import CoveragePass
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_signal import ThesisSignal
from app.services.claim_review import ClaimCheckInState, compute_check_in
from app.services.valuation import compute_pnl


@dataclass
class HoldingPulse:
    holding_id: uuid.UUID
    ticker: str
    name: str
    pulse_status: str  # intact | watch | review
    pulse_basis: str  # evidence | case_review | missing_case | none
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
    unresolved_event_count: int = 0
    # How many pipeline sources produced at least one candidate on the most
    # recent monitoring pass for this holding — powers the passive-receipt line
    # ("checked X ago · N sources · <state>") that proves the quiet is
    # informed, not lazy. None when we haven't run a pass yet.
    sources_count: int | None = None


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
    # Single valuation path. When there's no market value yet, fall back to cost
    # (0% P&L) rather than inventing a number.
    value = _to_float(holding.current_value)
    if value is None:
        return 0.0 if _to_float(holding.average_cost_basis) else None
    _, pnl_pct = compute_pnl(value, holding.quantity, holding.average_cost_basis)
    return pnl_pct


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


def _requires_decision(event: MonitoringEvent) -> bool:
    """Return whether an unreviewed event belongs in the decision inbox.

    Direction wins over headline severity: a warning-level article that
    supports the written case is evidence, but it is not an unresolved call.
    Legacy rows without a verdict retain the old severity fallback.
    """
    if event.verdict in {"supports", "neutral"}:
        return False
    return event.severity in {"warning", "thesis_breaking"}


def _unique_events(events: list[MonitoringEvent]) -> list[MonitoringEvent]:
    """Keep the database order while preventing duplicate claim-state events."""
    return list({event.id: event for event in events}.values())


def _events_from_states(
    states: list[ClaimCheckInState],
    *,
    pending_only: bool = False,
) -> list[MonitoringEvent]:
    selected = [state for state in states if state.needs_review] if pending_only else states
    return _unique_events([
        event
        for state in selected
        for event in state.threatens_events
    ])


async def _latest_sources_by_thesis(
    db: AsyncSession, thesis_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """For each thesis, count how many pipeline sources were queried on the
    latest coverage pass for that thesis.

    Scope the lookup by thesis, not holding, so a rewritten active thesis
    doesn't inherit a passive receipt from an older invalidated thesis on the
    same holding.
    """
    if not thesis_ids:
        return {}

    # Pull one row per thesis: the most recent coverage pass, whatever its
    # trigger (check_now / daily monitoring_run / edgar_watch all count).
    subquery = (
        select(
            CoveragePass.thesis_id,
            func.max(CoveragePass.started_at).label("latest_started_at"),
        )
        .where(CoveragePass.thesis_id.in_(thesis_ids))
        .group_by(CoveragePass.thesis_id)
        .subquery()
    )
    latest_result = await db.execute(
        select(CoveragePass.thesis_id, CoveragePass.payload)
        .join(
            subquery,
            (CoveragePass.thesis_id == subquery.c.thesis_id)
            & (CoveragePass.started_at == subquery.c.latest_started_at),
        )
    )

    counts: dict[uuid.UUID, int] = {}
    for thesis_id, payload in latest_result.all():
        if thesis_id is None:
            continue
        if not isinstance(payload, dict):
            continue
        sources = payload.get("sources")
        if not isinstance(sources, dict):
            continue
        # "Non-zero source" = the source was queried AND returned at least one
        # candidate. A source that erred with zero candidates still counts as
        # "checked" for our purposes — the number is meant to convey "we
        # tried these," not "these bore fruit."
        count = 0
        for source in sources.values():
            if not isinstance(source, dict):
                continue
            if source.get("queried") is False:
                continue
            if source.get("candidates_returned", 0) > 0 or source.get("error"):
                count += 1
            elif source.get("queried"):
                # Queried, returned nothing, no error — still counts as "looked."
                count += 1
        counts[thesis_id] = count
    return counts


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
    active_thesis_ids = [thesis.id for thesis in thesis_by_holding.values()]

    # Portfolio and position review must share one definition of "unresolved."
    # Claim check-in state applies per-claim review cutoffs and accumulation
    # thresholds; reading MonitoringEvent rows directly caused the dashboard to
    # resurface evidence after the investor had already ruled on it.
    check_in_by_thesis: dict[uuid.UUID, list[ClaimCheckInState]] = {}
    all_events: list[MonitoringEvent] = []
    for thesis in thesis_by_holding.values():
        states = await compute_check_in(db, thesis)
        check_in_by_thesis[thesis.id] = states
        all_events.extend(
            event
            for state in states
            for event in state.supports_events + state.threatens_events + state.neutral_events
        )
    all_events = _unique_events(all_events)

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
    sources_count_by_thesis = await _latest_sources_by_thesis(db, active_thesis_ids)

    for holding in holdings:
        thesis = thesis_by_holding.get(holding.id)
        states = check_in_by_thesis.get(thesis.id, []) if thesis else []
        pending_states = [state for state in states if state.needs_review]
        current_threats = _events_from_states(states)
        pending_events = _events_from_states(states, pending_only=True)
        pressure_events = [event for event in current_threats if _requires_decision(event)]
        # Pending claim decisions may be triggered by four lower-severity
        # threats, so use all of that claim's evidence once its threshold trips.
        decision_events = pending_events if pending_states else pressure_events
        pending_decision_count = len(pending_states)
        recent_event_count = sum(
            1
            for event in decision_events
            if event.created_at is not None and _normalize_datetime(event.created_at) >= cutoff
        )

        # P&L percent
        pnl_pct = _compute_pnl_pct(holding)

        # Prefer the explicit monitored-at stamp (set on every check, even quiet
        # ones) so "checked X ago" is truthful; fall back to the last event time.
        last_checked = _normalize_datetime(holding.last_monitored_at) or last_checked_map.get(holding.id)
        latest_event_at = _normalize_datetime(decision_events[0].created_at) if decision_events else None

        if not thesis:
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status="review",
                pulse_basis="missing_case",
                reason="No thesis — this position has no documented reason to exist.",
                latest_event_summary=None,
                days_since_thesis_update=None,
                has_thesis=False,
                latest_event_at=latest_event_at,
                urgency_score=100,
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=recent_event_count,
                unresolved_event_count=0,
                sources_count=None,
            ))
            continue

        days_since_update = _days_since_update(thesis.updated_at, now=now)
        latest_summary = _combined_event_summary(
            decision_events,
            now=now,
            signal_labels=signal_labels,
            ticker=holding.ticker,
        )
        latest_assumption = (
            _event_assumption_label(
                decision_events[0],
                signal_labels=signal_labels,
                ticker=holding.ticker,
            )
            if decision_events
            else None
        )
        stale_status, stale_reason = _stale_pressure(thesis, days_since_update=days_since_update)

        # Determine pulse
        has_pending_evidence = bool(pending_states)
        if has_pending_evidence or thesis.status == "needs_review":
            pulse_status = "review"
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                pulse_basis="evidence",
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
                    recent_event_count=recent_event_count,
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=recent_event_count,
                unresolved_event_count=pending_decision_count,
                sources_count=sources_count_by_thesis.get(thesis.id),
            ))
        elif pressure_events or stale_status in {"watch", "review"}:
            has_changed_evidence = bool(pressure_events)
            pulse_status = "watch" if has_changed_evidence else stale_status or "watch"
            reason = latest_summary if has_changed_evidence else stale_reason
            reason = reason or f"Thesis is {days_since_update} days old — consider reviewing."
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                pulse_basis="evidence" if has_changed_evidence else "case_review",
                reason=reason,
                assumption_label=latest_assumption,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
                latest_event_at=latest_event_at,
                urgency_score=_urgency_score(
                    pulse_status=pulse_status,
                    recent_event_count=recent_event_count,
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=recent_event_count,
                unresolved_event_count=0,
                sources_count=sources_count_by_thesis.get(thesis.id),
            ))
        else:
            pulse_status = "intact"
            pulses.append(HoldingPulse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                pulse_status=pulse_status,
                pulse_basis="none",
                reason="Nothing meaningful changed — your assumptions still hold.",
                assumption_label=latest_assumption,
                latest_event_summary=latest_summary,
                days_since_thesis_update=days_since_update,
                has_thesis=True,
                latest_event_at=latest_event_at,
                urgency_score=_urgency_score(
                    pulse_status=pulse_status,
                    recent_event_count=recent_event_count,
                    latest_event_at=latest_event_at,
                    days_since_update=days_since_update,
                ),
                pnl_pct=pnl_pct,
                last_checked_at=last_checked,
                recent_event_count=recent_event_count,
                unresolved_event_count=0,
                sources_count=sources_count_by_thesis.get(thesis.id),
            ))

    return pulses, _next_sunday_8am()
