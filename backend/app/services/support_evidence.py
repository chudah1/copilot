"""Supporting evidence: monitoring events where the classifier judged the
signal as validating the thesis rather than threatening it.

Split off from the main event stream so the UI can render "your thesis
was validated" as a distinct positive surface — a user seeing supporting
evidence mixed in with threat cards mentally registers everything as
"another thing to deal with." The digest and the position tab both
call in.

Kept intentionally strict: one supporting item per position per week,
because the goal is emotional balance ("sometimes my thesis is being
validated"), not a highlight reel. Two positives on the same holding in
one week starts to feel like the pipeline flattering the user rather
than telling them something real.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_signal import ThesisSignal


# Hard cap per surface: the point is occasional reassurance, not a wall of
# green cards. Higher than the reviewed-this-week cap because supports events
# are typically fewer and more meaningful — but still small.
DEFAULT_MAX_SUPPORTING_ITEMS = 3


@dataclass
class SupportingItem:
    """One curated supporting-evidence item, ready for API + digest render."""
    event_id: uuid.UUID
    holding_id: uuid.UUID
    ticker: str
    title: str
    summary: str
    ai_analysis: str | None
    evidence_summary: str | None
    severity: str
    event_type: str
    source_url: str | None
    created_at: datetime
    assumption_label: str | None
    # Signal/claim IDs kept so the frontend can navigate to the thesis
    # pillar this evidence supports.
    claim_id: uuid.UUID | None
    signal_id: uuid.UUID | None


def _severity_rank(severity: str | None) -> int:
    """Higher rank = stronger positive signal. A thesis_breaking supports
    event is an unusually strong validation ("management confirmed the
    moat is widening") and should win over a routine info-tier support."""
    return {"thesis_breaking": 3, "warning": 2, "info": 1}.get(severity or "info", 0)


def _binding_strength(event: MonitoringEvent) -> int:
    """Events tied to a specific claim/signal beat unbound generic positives.
    Unbound supports read as "some good news" — bound ones read as "this
    specific thesis pillar was reinforced," which is the shape we want."""
    return int(bool(event.claim_id)) + int(bool(event.signal_id))


def _to_supporting_item(
    event: MonitoringEvent,
    *,
    ticker: str,
    assumption_label: str | None,
) -> SupportingItem:
    return SupportingItem(
        event_id=event.id,
        holding_id=event.holding_id,
        ticker=ticker,
        title=event.title,
        summary=event.summary,
        ai_analysis=event.ai_analysis,
        evidence_summary=event.evidence_summary,
        severity=event.severity,
        event_type=event.event_type,
        source_url=event.source_url,
        created_at=event.created_at if event.created_at.tzinfo else event.created_at.replace(tzinfo=timezone.utc),
        assumption_label=assumption_label,
        claim_id=event.claim_id,
        signal_id=event.signal_id,
    )


async def load_supporting_events_for_holdings(
    db: AsyncSession,
    *,
    holding_ids: list[uuid.UUID],
    thesis_ids: list[uuid.UUID] | None = None,
    period_start: datetime,
    period_end: datetime | None = None,
) -> list[MonitoringEvent]:
    """Fetch supporting-verdict events for the given holdings in the window."""
    if not holding_ids or thesis_ids == []:
        return []
    stmt = (
        select(MonitoringEvent)
        .where(
            MonitoringEvent.holding_id.in_(holding_ids),
            MonitoringEvent.verdict == "supports",
            MonitoringEvent.created_at >= period_start,
        )
        .order_by(MonitoringEvent.created_at.desc())
    )
    if thesis_ids is not None:
        stmt = stmt.where(MonitoringEvent.thesis_id.in_(thesis_ids))
    if period_end is not None:
        stmt = stmt.where(MonitoringEvent.created_at <= period_end)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def curate_supporting_items(
    events: Iterable[MonitoringEvent],
    *,
    ticker_by_holding: dict[uuid.UUID, str],
    label_by_event: dict[uuid.UUID, str | None] | None = None,
    max_items: int = DEFAULT_MAX_SUPPORTING_ITEMS,
    max_per_holding: int = 1,
) -> list[SupportingItem]:
    """Pick the strongest supporting-evidence items across holdings.

    Preferences:
      - stronger severity beats info-tier
      - claim/signal-bound beats unbound
      - more recent beats older
    Constraints:
      - max_per_holding caps items per position (1 by default — the whole
        point is emotional balance, not a green highlight reel)
      - max_items caps the total surface size
    """
    label_by_event = label_by_event or {}
    events_list = list(events)
    if not events_list:
        return []

    def _score(event: MonitoringEvent) -> tuple[int, int, float]:
        created = event.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (_severity_rank(event.severity), _binding_strength(event), created.timestamp())

    events_sorted = sorted(events_list, key=_score, reverse=True)

    counts_per_holding: dict[uuid.UUID, int] = {}
    picked: list[SupportingItem] = []
    for event in events_sorted:
        if len(picked) >= max_items:
            break
        if counts_per_holding.get(event.holding_id, 0) >= max_per_holding:
            continue
        ticker = ticker_by_holding.get(event.holding_id)
        if not ticker:
            continue
        assumption_label = label_by_event.get(event.id)
        picked.append(_to_supporting_item(event, ticker=ticker, assumption_label=assumption_label))
        counts_per_holding[event.holding_id] = counts_per_holding.get(event.holding_id, 0) + 1
    return picked


async def load_curated_supporting_items_for_holding(
    db: AsyncSession,
    *,
    holding: Holding,
    window_days: int,
    max_items: int = 1,
) -> list[SupportingItem]:
    """Convenience wrapper for the single-holding API endpoint. Applies the
    same curation rules the digest uses so the two surfaces agree."""
    thesis_ids_result = await db.execute(
        select(Thesis.id).where(
            Thesis.holding_id == holding.id,
            Thesis.user_id == holding.user_id,
            Thesis.status.in_(["active", "draft", "needs_review"]),
        )
    )
    thesis_ids = [row[0] for row in thesis_ids_result.all()]
    if not thesis_ids:
        return []

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=window_days)
    events = await load_supporting_events_for_holdings(
        db,
        holding_ids=[holding.id],
        thesis_ids=thesis_ids,
        period_start=period_start,
        period_end=now,
    )
    signal_ids = {event.signal_id for event in events if event.signal_id is not None}
    label_by_event: dict[uuid.UUID, str | None] = {}
    if signal_ids:
        signals_result = await db.execute(
            select(ThesisSignal).where(ThesisSignal.id.in_(signal_ids))
        )
        label_by_signal = {
            signal.id: signal.signal_label
            for signal in signals_result.scalars().all()
            if signal.signal_label
        }
        label_by_event = {
            event.id: label_by_signal.get(event.signal_id)
            for event in events
            if event.signal_id in label_by_signal
        }
    return curate_supporting_items(
        events,
        ticker_by_holding={holding.id: holding.ticker},
        label_by_event=label_by_event,
        max_items=max_items,
        max_per_holding=1,
    )
