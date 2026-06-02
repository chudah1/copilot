"""Capture half of the decision-mirror loop.

When a user makes a conviction call (a verdict on a fired monitoring event, or a
periodic re-underwrite), snapshot the decision + what they were betting on, using
only values already in hand — no network fetch. The reflective view and the
earnings-anchored resolution job are built later; this just makes the data accrue
from day one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_snapshot import DecisionSnapshot
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis

logger = logging.getLogger(__name__)

# Raw 5 review verdicts -> the three display buckets, each a distinct counterfactual.
VERDICT_BUCKET = {
    "reaffirmed": "held",
    "lowered_confidence": "held",
    "invalidated": "exited",
    "ignored": "dismissed",
    "not_relevant": "dismissed",
}

# Quarterly re-underwrite answers ("do you still believe this?") -> buckets. A
# whole-thesis re-underwrite has no signal to dismiss, so only held / exited.
QUARTERLY_BUCKET = {
    "yes_absolutely": "held",
    "probably": "held",
    "not_sure": "held",   # wavering hold (thesis moves to needs_review)
    "no": "exited",
}

# Coarse benchmark per account/native currency for the eventual "vs market" read.
# Ticker only — the price is reconstructed historically at resolution time.
_BENCHMARK_BY_CCY = {
    "USD": "SPY",
    "GBP": "ISF.L",   # iShares FTSE 100
    "GBp": "ISF.L",
    "EUR": "EXSA.DE",  # iShares STOXX Europe 600
    "CAD": "XIC.TO",
}
_DEFAULT_BENCHMARK = "SPY"


def _benchmark_for(currency: str | None) -> str:
    return _BENCHMARK_BY_CCY.get(currency or "", _DEFAULT_BENCHMARK)


async def _next_test_at(db: AsyncSession, ticker: str, *, now: datetime) -> datetime | None:
    """Next earnings date for the ticker (a cheap local lookup, not a fetch).
    Anchors resolution; null falls back to a 90-day soft read later."""
    row = (
        await db.execute(
            select(EarningsCalendar.report_date).where(EarningsCalendar.ticker == ticker.upper())
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    report = row if row.tzinfo is not None else row.replace(tzinfo=timezone.utc)
    return report if report >= now else None


async def _persist_snapshot(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    verdict: str,
    bucket: str,
    decision_source: str,
    bet_text: str | None,
    event: MonitoringEvent | None,
    notes: str | None,
    now: datetime,
) -> DecisionSnapshot:
    """Build + add the snapshot shared by every capture site. The only differences
    between sites are the verdict/bucket/source, the bet text, and the event-linked
    fields (null for a whole-thesis re-underwrite)."""
    interpretation = thesis.interpretation or {}
    snapshot = DecisionSnapshot(
        user_id=thesis.user_id,
        thesis_id=thesis.id,
        holding_id=holding.id,
        monitoring_event_id=event.id if event else None,
        claim_id=event.claim_id if event else None,
        signal_id=event.signal_id if event else None,
        verdict=verdict,
        bucket=bucket,
        decision_source=decision_source,
        decided_at=now,
        price_native=holding.current_price,
        value_gbp=holding.current_value,
        currency=holding.currency,
        benchmark_ticker=_benchmark_for(holding.currency),
        next_test_at=await _next_test_at(db, holding.ticker, now=now),
        bet_text=bet_text,
        condition_snapshot={
            "watch_hints": interpretation.get("watch_hints"),
            "monitorability": interpretation.get("monitorability"),
            "triggering_evidence": event.raw_data if event else None,
            "event_type": event.event_type if event else None,
            "evidence_type": event.evidence_type if event else None,
            "severity": event.severity if event else None,
            "verdict_note": notes,
        },
    )
    db.add(snapshot)
    return snapshot


async def capture_event_decision(
    db: AsyncSession,
    *,
    thesis: Thesis,
    event: MonitoringEvent,
    action: str,
    notes: str | None = None,
    now: datetime | None = None,
) -> DecisionSnapshot | None:
    """Snapshot a verdict made on a fired monitoring event. Best-effort: returns
    None (and never raises) on anything unusual, so a capture problem can't break
    the user's decision."""
    try:
        bucket = VERDICT_BUCKET.get(action)
        if bucket is None:
            return None  # not one of the five conviction verdicts
        now = now or datetime.now(timezone.utc)
        holding = (
            await db.execute(select(Holding).where(Holding.id == event.holding_id))
        ).scalar_one_or_none()
        if holding is None:
            return None
        return await _persist_snapshot(
            db, thesis=thesis, holding=holding, verdict=action, bucket=bucket,
            decision_source="event_review",
            bet_text=(event.evidence_summary or event.summary or event.title),
            event=event, notes=notes, now=now,
        )
    except Exception:
        logger.exception("Failed to capture decision snapshot for event %s", getattr(event, "id", None))
        return None


async def capture_quarterly_decision(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding | None = None,
    response_value: str,
    notes: str | None = None,
    now: datetime | None = None,
) -> DecisionSnapshot | None:
    """Snapshot a quarterly re-underwrite ("do you still believe this?"). Same
    best-effort contract as capture_event_decision. No event/claim/signal — the
    bet is the thesis itself, so there's no triggering evidence to record."""
    try:
        bucket = QUARTERLY_BUCKET.get(response_value)
        if bucket is None:
            return None
        now = now or datetime.now(timezone.utc)
        if holding is None:
            holding = (
                await db.execute(select(Holding).where(Holding.id == thesis.holding_id))
            ).scalar_one_or_none()
        if holding is None:
            return None
        return await _persist_snapshot(
            db, thesis=thesis, holding=holding, verdict=response_value, bucket=bucket,
            decision_source="quarterly_review", bet_text=thesis.why_own_it,
            event=None, notes=notes, now=now,
        )
    except Exception:
        logger.exception("Failed to capture quarterly decision snapshot for thesis %s", getattr(thesis, "id", None))
        return None
