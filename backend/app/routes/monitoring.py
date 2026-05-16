import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import get_current_user
from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.schemas.holding import CheckNowResponse, MarketSnapshotResponse
from app.schemas.monitoring_event import (
    MonitoringEventResponse,
    MonitoringEventReviewResponse,
    ReviewMonitoringEventRequest,
)
from app.services.check_now import run_check_now
from app.services.conviction_log import REASON_CREATED
from app.services.monitoring_review import review_monitoring_event

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/holdings/{holding_id}/events", response_model=list[MonitoringEventResponse])
async def get_events_for_holding(holding_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MonitoringEvent)
        .where(
            MonitoringEvent.holding_id == holding_id,
            MonitoringEvent.holding.has(user_id=user.id)
        )
        .options(selectinload(MonitoringEvent.reviews))
        .order_by(MonitoringEvent.created_at.desc())
        .limit(50)
    )
    events = result.scalars().all()

    # Batch-load signal labels for all events that have a signal_id
    signal_ids = {event.signal_id for event in events if event.signal_id is not None}
    signal_labels: dict[uuid.UUID, str | None] = {}
    if signal_ids:
        signals_result = await db.execute(
            select(ThesisSignal).where(ThesisSignal.id.in_(signal_ids))
        )
        for signal in signals_result.scalars().all():
            signal_labels[signal.id] = signal.signal_label

    return [
        MonitoringEventResponse(
            id=event.id,
            holding_id=event.holding_id,
            thesis_id=event.thesis_id,
            event_type=event.event_type,
            severity=event.severity,
            title=event.title,
            summary=event.summary,
            source_url=event.source_url,
            ai_analysis=event.ai_analysis,
            review_action=event.reviews[0].action if event.reviews else None,
            review_notes=event.reviews[0].notes if event.reviews else None,
            claim_id=event.claim_id,
            signal_id=event.signal_id,
            signal_label=signal_labels.get(event.signal_id) if event.signal_id else None,
            evidence_type=event.evidence_type,
            evidence_summary=event.evidence_summary,
            verdict=event.verdict,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.post("/events/{event_id}/review", response_model=MonitoringEventReviewResponse)
async def review_event(
    event_id: uuid.UUID,
    body: ReviewMonitoringEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(
        select(MonitoringEvent)
        .join(Thesis, Thesis.id == MonitoringEvent.thesis_id)
        .where(
            MonitoringEvent.id == event_id,
            Thesis.user_id == user.id,
        )
        .options(selectinload(MonitoringEvent.thesis))
    )
    event = event_result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring event not found")
    if event.thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    try:
        review = await review_monitoring_event(
            db,
            event=event,
            thesis=event.thesis,
            action=body.action,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Compute reason_age_days from conviction log
    reason_age_days = None
    first_entry_result = await db.execute(
        select(ConvictionLogEntry)
        .where(
            ConvictionLogEntry.thesis_id == event.thesis.id,
            ConvictionLogEntry.entry_type == REASON_CREATED,
        )
        .order_by(ConvictionLogEntry.created_at.asc())
        .limit(1)
    )
    first_entry = first_entry_result.scalar_one_or_none()
    if first_entry is not None:
        from datetime import datetime, timezone
        created = first_entry.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        reason_age_days = (datetime.now(timezone.utc) - created).days

    return MonitoringEventReviewResponse(
        id=review.id,
        monitoring_event_id=review.monitoring_event_id,
        thesis_id=review.thesis_id,
        action=review.action,
        notes=review.notes,
        created_at=review.created_at,
        thesis=event.thesis,
        reason_age_days=reason_age_days,
    )


@router.post("/holdings/{holding_id}/check-now", response_model=CheckNowResponse)
async def check_now(
    holding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Load holding and verify ownership
    holding_result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id)
    )
    holding = holding_result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    # Load active thesis for this holding
    thesis_result = await db.execute(
        select(Thesis).where(
            Thesis.holding_id == holding_id,
            Thesis.user_id == user.id,
            Thesis.status.in_(["active", "draft", "needs_review"]),
        ).order_by(Thesis.created_at.desc()).limit(1)
    )
    thesis = thesis_result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active thesis")

    result = await run_check_now(holding, thesis, db)

    snapshot_response = None
    if result.snapshot is not None:
        snapshot_response = MarketSnapshotResponse(
            current_price=result.snapshot.current_price,
            price_change_pct=result.snapshot.price_change_pct,
            cost_basis=result.snapshot.cost_basis,
            pnl=result.snapshot.pnl,
            pnl_pct=result.snapshot.pnl_pct,
            sector=result.snapshot.sector,
            pe_ratio=result.snapshot.pe_ratio,
            market_cap=result.snapshot.market_cap,
            upcoming_earnings_date=result.snapshot.upcoming_earnings_date,
            recent_news_count=result.snapshot.recent_news_count,
            watch_hints_ok=result.snapshot.watch_hints_ok,
            watch_hints_total=result.snapshot.watch_hints_total,
            checked_at=result.snapshot.checked_at,
        )

    return CheckNowResponse(
        status=result.status,
        events_created=result.events_created,
        next_available_at=result.next_available_at,
        snapshot=snapshot_response,
    )
