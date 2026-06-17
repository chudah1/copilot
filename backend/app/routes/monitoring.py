import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.services.relevance import compute_relevance_metrics
from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.monitoring_gap import MonitoringGap
from app.models.thesis import Thesis
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.schemas.holding import CheckNowResponse, MarketSnapshotResponse
from app.schemas.monitoring_event import (
    MonitoringEventResponse,
    MonitoringEventReviewResponse,
    ReviewMonitoringEventRequest,
)
from app.schemas.coverage import CoveragePassResponse, SignalCoverageResponse, ThesisCoverageResponse
from app.schemas.monitoring_gap import MonitoringGapResponse
from app.services.check_now import run_check_now
from app.services.conviction_log import REASON_CREATED
from app.services.coverage import (
    DEFAULT_COVERAGE_WINDOW_DAYS,
    compute_thesis_coverage,
    latest_coverage_passes,
)
from app.services.monitoring_review import review_monitoring_event

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _normalize_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _latest_review(event: MonitoringEvent):
    return event.reviews[0] if event.reviews else None


def _multi_binding_from_raw(event: MonitoringEvent) -> tuple[list[uuid.UUID], list[str], dict[uuid.UUID, float]]:
    """Pull matched_signal_ids / matched_signal_labels / match_confidence_by_signal
    out of the event's raw evidence payload. Falls back to the single primary
    signal_id when the multi-binding isn't present (e.g. for events persisted
    before this field rolled out)."""
    raw = event.raw_data or {}
    evidence = raw.get("evidence") if isinstance(raw, dict) else None
    matched_ids_raw = evidence.get("matched_signal_ids") if isinstance(evidence, dict) else None
    matched_labels_raw = evidence.get("matched_signal_labels") if isinstance(evidence, dict) else None
    confidence_raw = evidence.get("match_confidence_by_signal") if isinstance(evidence, dict) else None
    matched_ids: list[uuid.UUID] = []
    if isinstance(matched_ids_raw, list):
        for value in matched_ids_raw:
            try:
                matched_ids.append(uuid.UUID(str(value)))
            except (ValueError, TypeError):
                continue
    matched_labels = [str(lbl) for lbl in (matched_labels_raw or []) if isinstance(lbl, str)] if isinstance(matched_labels_raw, list) else []
    confidence: dict[uuid.UUID, float] = {}
    if isinstance(confidence_raw, dict):
        for key, value in confidence_raw.items():
            try:
                confidence[uuid.UUID(str(key))] = float(value)
            except (ValueError, TypeError):
                continue
    if not matched_ids and event.signal_id is not None:
        matched_ids = [event.signal_id]
    return matched_ids, matched_labels, confidence


def _to_event_response(
    event: MonitoringEvent,
    *,
    signal_labels: dict[uuid.UUID, str | None],
) -> MonitoringEventResponse:
    latest_review = _latest_review(event)
    matched_ids, matched_labels, match_confidence = _multi_binding_from_raw(event)
    # If the persisted labels list is empty but we have ids and a label cache,
    # populate from the cache so the UI can render labels without re-querying.
    if not matched_labels and matched_ids:
        matched_labels = [signal_labels[sid] for sid in matched_ids if signal_labels.get(sid)]
    return MonitoringEventResponse(
        id=event.id,
        holding_id=event.holding_id,
        thesis_id=event.thesis_id,
        event_type=event.event_type,
        severity=event.severity,
        title=event.title,
        summary=event.summary,
        source_url=event.source_url,
        ai_analysis=event.ai_analysis,
        review_action=latest_review.action if latest_review else None,
        review_notes=latest_review.notes if latest_review else None,
        claim_id=event.claim_id,
        signal_id=event.signal_id,
        signal_label=signal_labels.get(event.signal_id) if event.signal_id else None,
        matched_signal_ids=matched_ids,
        matched_signal_labels=matched_labels,
        match_confidence_by_signal=match_confidence,
        evidence_type=event.evidence_type,
        evidence_summary=event.evidence_summary,
        verdict=event.verdict,
        created_at=event.created_at,
    )


async def _load_signal_labels(
    db: AsyncSession,
    *,
    events: list[MonitoringEvent],
) -> dict[uuid.UUID, str | None]:
    # Collect the primary signal_id and every id from the multi-binding list so
    # we can resolve labels for the full set in one query.
    signal_ids: set[uuid.UUID] = set()
    for event in events:
        if event.signal_id is not None:
            signal_ids.add(event.signal_id)
        matched_ids, _, _ = _multi_binding_from_raw(event)
        signal_ids.update(matched_ids)
    if not signal_ids:
        return {}

    signals_result = await db.execute(
        select(ThesisSignal).where(ThesisSignal.id.in_(signal_ids))
    )
    return {signal.id: signal.signal_label for signal in signals_result.scalars().all()}


async def _load_reviewable_event(
    db: AsyncSession,
    *,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
) -> MonitoringEvent | None:
    event_result = await db.execute(
        select(MonitoringEvent)
        .join(Thesis, Thesis.id == MonitoringEvent.thesis_id)
        .where(
            MonitoringEvent.id == event_id,
            Thesis.user_id == user_id,
        )
        .options(selectinload(MonitoringEvent.thesis))
    )
    return event_result.scalar_one_or_none()


async def _reason_age_days_for_thesis(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
) -> int | None:
    first_entry_result = await db.execute(
        select(ConvictionLogEntry)
        .where(
            ConvictionLogEntry.thesis_id == thesis_id,
            ConvictionLogEntry.entry_type == REASON_CREATED,
        )
        .order_by(ConvictionLogEntry.created_at.asc())
        .limit(1)
    )
    first_entry = first_entry_result.scalar_one_or_none()
    if first_entry is None:
        return None

    created = _normalize_datetime(first_entry.created_at)
    return (datetime.now(timezone.utc) - created).days


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
    signal_labels = await _load_signal_labels(db, events=events)
    return [_to_event_response(event, signal_labels=signal_labels) for event in events]


@router.post("/events/{event_id}/review", response_model=MonitoringEventReviewResponse)
async def review_event(
    event_id: uuid.UUID,
    body: ReviewMonitoringEventRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await _load_reviewable_event(db, event_id=event_id, user_id=user.id)
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

    await db.commit()
    await db.refresh(review)
    await db.refresh(event.thesis)
    reason_age_days = await _reason_age_days_for_thesis(db, thesis_id=event.thesis.id)

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

    try:
        result = await run_check_now(holding, thesis, db)
    except RuntimeError as exc:
        if "market_data_unavailable" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Market data is temporarily unavailable (rate limit). Wait a moment and try again.",
            ) from exc
        raise

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


@router.get("/holdings/{holding_id}/decisions")
async def get_decisions_for_holding_endpoint(
    holding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The decision-mirror calls for one position — each with its read (if the bet
    has been tested) or its next-test countdown (if still open)."""
    holding = (
        await db.execute(select(Holding).where(Holding.id == holding_id, Holding.user_id == user.id))
    ).scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    from app.services.decision_mirror import get_decisions_for_holding

    return await get_decisions_for_holding(db, user.id, holding_id, now=datetime.now(timezone.utc))


@router.get("/gaps", response_model=list[MonitoringGapResponse])
async def get_monitoring_gaps(
    thesis_id: uuid.UUID | None = Query(default=None),
    since: datetime | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return monitoring gaps (source failures) for the authenticated user's theses."""
    stmt = (
        select(MonitoringGap)
        .join(Thesis, MonitoringGap.thesis_id == Thesis.id, isouter=True)
        .where(
            (Thesis.user_id == user.id) | (MonitoringGap.thesis_id.is_(None))
        )
        .order_by(MonitoringGap.failed_at.desc())
        .limit(200)
    )
    if thesis_id is not None:
        stmt = stmt.where(MonitoringGap.thesis_id == thesis_id)
    if since is not None:
        normalized_since = _normalize_datetime(since)
        stmt = stmt.where(MonitoringGap.failed_at >= normalized_since)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/theses/{thesis_id}/coverage", response_model=ThesisCoverageResponse)
async def get_thesis_coverage(
    thesis_id: uuid.UUID,
    window_days: int = Query(default=DEFAULT_COVERAGE_WINDOW_DAYS, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-signal coverage diagnostics: for each active signal on the thesis,
    did any monitoring event in the window touch it? Surfaces "thin coverage"
    as concrete uncovered-signal counts instead of vibes."""
    thesis_result = await db.execute(
        select(Thesis).where(Thesis.id == thesis_id, Thesis.user_id == user.id)
    )
    thesis = thesis_result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thesis not found")

    report = await compute_thesis_coverage(db, thesis_id, window_days=window_days)
    return ThesisCoverageResponse(
        thesis_id=report.thesis_id,
        window_start=report.window_start,
        window_end=report.window_end,
        covered_count=report.covered_count,
        uncovered_count=report.uncovered_count,
        inactive_signal_count=report.inactive_signal_count,
        no_decomposition=report.no_decomposition,
        signals=[
            SignalCoverageResponse(
                signal_id=s.signal_id,
                signal_label=s.signal_label,
                signal_type=s.signal_type,
                claim_id=s.claim_id,
                claim_text=s.claim_text,
                covered=s.covered,
                matched_event_count=s.matched_event_count,
                last_matched_at=s.last_matched_at,
                last_event_id=s.last_event_id,
                last_event_severity=s.last_event_severity,
                max_confidence=s.max_confidence,
                is_strong_binding=s.is_strong_binding,
            )
            for s in report.signals
        ],
    )


@router.get("/theses/{thesis_id}/coverage/passes", response_model=list[CoveragePassResponse])
async def get_thesis_coverage_passes(
    thesis_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-pass funnel diagnostics — for each recent pipeline pass against
    this thesis, the source query results and stage-by-stage candidate
    counts. Answers Codex's 'which stage failed' question concretely."""
    thesis_result = await db.execute(
        select(Thesis).where(Thesis.id == thesis_id, Thesis.user_id == user.id)
    )
    if thesis_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thesis not found")

    passes = await latest_coverage_passes(db, thesis_id, limit=limit)
    return [
        CoveragePassResponse(
            id=p.id,
            thesis_id=p.thesis_id,
            holding_id=p.holding_id,
            run_id=p.run_id,
            triggered_by=p.triggered_by,
            started_at=p.started_at,
            finished_at=p.finished_at,
            payload=p.payload,
            created_at=p.created_at,
        )
        for p in passes
    ]


@router.get("/relevance")
async def relevance_metrics(
    days: int = Query(14, ge=1, le=90),
    x_metrics_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Global signal-quality read: of the events users reviewed, what fraction did
    they mark "not relevant", broken down by source. Gated by the X-Metrics-Token
    header (matched against settings.metrics_token); disabled if no token is set.

    This is an ops endpoint, not user-facing — it deliberately uses a shared token
    rather than JWT so it can be curled while watching the first users go live.
    """
    if not settings.metrics_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if x_metrics_token != settings.metrics_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid metrics token")

    metrics = await compute_relevance_metrics(db, days=days)
    return metrics.to_dict()
