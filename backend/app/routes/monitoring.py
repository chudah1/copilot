import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import get_current_user
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.holding import CheckNowResponse
from app.schemas.monitoring_event import (
    MonitoringEventResponse,
    MonitoringEventReviewResponse,
    ReviewMonitoringEventRequest,
)
from app.services.check_now import run_check_now
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

    return MonitoringEventReviewResponse(
        id=review.id,
        monitoring_event_id=review.monitoring_event_id,
        thesis_id=review.thesis_id,
        action=review.action,
        notes=review.notes,
        created_at=review.created_at,
        thesis=event.thesis,
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

    return CheckNowResponse(
        status=result.status,
        events_created=result.events_created,
        next_available_at=result.next_available_at,
    )
