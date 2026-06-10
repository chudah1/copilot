import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.user import User
from app.schemas.thesis import (
    AssistThesisRequest,
    AssistThesisResponse,
    ClaimVerdictResponse,
    ConfirmDecompositionRequest,
    CounterThesisResponse,
    CreateThesisRequest,
    DebugDecomposeRequest,
    DebugDecomposeResponse,
    DraftThesisRequest,
    DraftThesisResponse,
    EarningsReviewResponse,
    HealthCheckResponse,
    HistoricalAuditResponse,
    InvalidateThesisRequest,
    ThesisDecompositionEnvelopeResponse,
    ThesisDecompositionResponse,
    ThesisResponse,
    UpdateThesisRequest,
)
from app.services.ai_thesis import assist_thesis, generate_counter_thesis, generate_initial_draft
from app.services.conviction_log import (
    POST_EARNINGS_REVIEW,
    REASON_CREATED,
    REASON_INVALIDATED,
    REASON_UPDATED,
    append_log_entry,
)
from app.services.decomposition import (
    PersistedDecompositionResult,
    confirm_decomposition_for_thesis,
    debug_compare_decomposition_providers,
    generate_decomposition_for_thesis,
)

router = APIRouter(prefix="/api/theses", tags=["theses"])


CURRENT_THESIS_STATUSES = {"draft", "active", "needs_review"}
VISIBLE_DECOMPOSITION_STATUSES = {"draft", "confirmed", "partially_confirmed"}


async def _get_latest_decomposition_record(
    db: AsyncSession,
    thesis_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ThesisDecomposition | None:
    result = await db.execute(
        select(ThesisDecomposition)
        .join(Thesis, Thesis.id == ThesisDecomposition.thesis_id)
        .where(
            ThesisDecomposition.thesis_id == thesis_id,
            Thesis.user_id == user_id,
        )
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
        .order_by(ThesisDecomposition.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _display_decomposition_status(status: str) -> str:
    # "pending" would be a lie — there's no background retry job
    return "failed" if status == "pending" else status


def _decomposition_envelope_from_result(result: PersistedDecompositionResult) -> ThesisDecompositionEnvelopeResponse:
    return ThesisDecompositionEnvelopeResponse(
        status=_display_decomposition_status(result.status),
        message=result.message,
        decomposition=result.decomposition,
    )


async def _load_user_thesis(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
    user_id: uuid.UUID,
    include_holding: bool = False,
) -> Thesis | None:
    query = select(Thesis).where(
        Thesis.id == thesis_id,
        Thesis.user_id == user_id,
    )
    if include_holding:
        query = query.options(selectinload(Thesis.holding))
    result = await db.execute(query)
    return result.scalar_one_or_none()


@router.post("", response_model=ThesisResponse, status_code=status.HTTP_201_CREATED)
async def create_thesis(
    body: CreateThesisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(
            Holding.id == body.holding_id,
            Holding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    existing_result = await db.execute(
        select(Thesis).where(
            Thesis.holding_id == holding.id,
            Thesis.user_id == current_user.id,
            Thesis.status.in_(["draft", "active", "needs_review"]),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A current thesis already exists for this holding")

    thesis = Thesis(
        holding_id=holding.id,
        user_id=current_user.id,
        status=body.status,
        thesis_kind=body.thesis_kind,
        why_own_it=body.why_own_it,
        must_remain_true=body.must_remain_true,
        what_would_change_my_mind=body.what_would_change_my_mind,
        confidence=body.confidence,
        review_cadence_days=body.review_cadence_days,
        ai_summary=body.ai_summary,
        interpretation=body.interpretation,
        source=body.source,
    )
    db.add(thesis)
    await db.flush()
    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=current_user.id,
        entry_type=REASON_CREATED,
        content=thesis.why_own_it,
        metadata={"confidence": thesis.confidence, "source": thesis.source},
    )
    from app.services.onboarding import mark_reason_written
    await mark_reason_written(db, current_user.id)
    await db.commit()
    await db.refresh(thesis)

    # Give the user a real first pulse now that the position has a monitorable
    # reason, instead of a dashboard that claims "all calm" before checking.
    if thesis.status in ("active", "draft", "needs_review"):
        from app.services.check_now import run_first_pulse
        background_tasks.add_task(run_first_pulse, current_user.id, holding.id)

    return thesis


@router.post("/assist", response_model=AssistThesisResponse)
async def assist_thesis_endpoint(
    body: AssistThesisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(
            Holding.id == body.holding_id,
            Holding.user_id == current_user.id,
        )
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    output = await assist_thesis(
        ticker=holding.ticker,
        name=holding.name,
        quantity=float(holding.quantity),
        average_cost=float(holding.average_cost_basis),
        draft_text=body.draft_text,
        why_own_it=body.why_own_it,
        must_remain_true=body.must_remain_true,
        what_would_change_my_mind=body.what_would_change_my_mind,
        allow_fallback=False,
    )
    if output is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to assist thesis draft")
    return AssistThesisResponse(
        why_own_it=output.why_own_it,
        must_remain_true=output.must_remain_true,
        what_would_change_my_mind=output.what_would_change_my_mind,
        ai_summary=output.ai_summary,
        interpretation=output.interpretation,
    )


@router.post("/draft", response_model=DraftThesisResponse)
async def draft_thesis_endpoint(
    body: DraftThesisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Simply generate a draft for the given ticker.
    # No holding validation required here, as it's just a text generation helper.
    output = await generate_initial_draft(ticker=body.ticker)
    return DraftThesisResponse(
        why_own_it=output["why_own_it"],
        must_remain_true=output["must_remain_true"],
        what_would_change_my_mind=output["what_would_change_my_mind"]
    )


@router.post("/debug/decompose", response_model=DebugDecomposeResponse)
async def debug_decompose(
    body: DebugDecomposeRequest,
    current_user: User = Depends(get_current_user),
):
    del current_user
    return await debug_compare_decomposition_providers(body.model_dump())


@router.post("/{thesis_id}/decompose", response_model=ThesisDecompositionEnvelopeResponse, status_code=status.HTTP_201_CREATED)
async def decompose_thesis(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(
        db,
        thesis_id=thesis_id,
        user_id=current_user.id,
        include_holding=True,
    )
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    result = await generate_decomposition_for_thesis(db=db, thesis=thesis, holding=thesis.holding)
    # generate_decomposition_for_thesis never hard-fails: on an unusable AI
    # result it persists a monitorable baseline floor. The pending/failed branch
    # is retained defensively but should no longer be reachable.
    if result.status in ("pending", "failed"):
        envelope = _decomposition_envelope_from_result(result)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=envelope.model_dump(mode="json"),
        )
    latest = await _get_latest_decomposition_record(db, thesis.id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create decomposition")
    return ThesisDecompositionEnvelopeResponse(
        status=_display_decomposition_status(latest.status),
        message=result.message,
        decomposition=latest,
    )


@router.post("/{thesis_id}/decomposition/confirm", response_model=ThesisDecompositionEnvelopeResponse)
async def confirm_decomposition(
    thesis_id: uuid.UUID,
    body: ConfirmDecompositionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(
        db,
        thesis_id=thesis_id,
        user_id=current_user.id,
        include_holding=True,
    )
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    decomposition = await confirm_decomposition_for_thesis(
        db,
        thesis=thesis,
        holding=thesis.holding,
        decomposition_id=body.decomposition_id,
        entity_confirmations=body.model_dump()["entities"],
        signal_confirmations=body.model_dump()["signals"],
    )
    if decomposition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decomposition not found")

    latest = await _get_latest_decomposition_record(db, thesis.id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decomposition not found")

    from app.services.check_now import run_historical_audit
    background_tasks.add_task(run_historical_audit, thesis_id)

    return ThesisDecompositionEnvelopeResponse(status=latest.status, message=None, decomposition=latest)


@router.get("/{thesis_id}/historical-audit", response_model=HistoricalAuditResponse)
async def get_historical_audit(
    thesis_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.check_now import run_historical_audit

    thesis = await _load_user_thesis(db, thesis_id=thesis_id, user_id=current_user.id)
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    if thesis.historical_audit_status is None:
        background_tasks.add_task(run_historical_audit, thesis_id)

    return HistoricalAuditResponse(
        status=thesis.historical_audit_status or "pending",
        results=thesis.historical_audit_results,
    )


@router.get("/{thesis_id}/decomposition", response_model=ThesisDecompositionEnvelopeResponse)
async def get_latest_decomposition(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(db, thesis_id=thesis_id, user_id=current_user.id)
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    latest = await _get_latest_decomposition_record(db, thesis_id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decomposition not found")
    if latest.status not in VISIBLE_DECOMPOSITION_STATUSES:
        return ThesisDecompositionEnvelopeResponse(
            status=_display_decomposition_status(latest.status),
            message=latest.last_error,
            decomposition=None,
        )
    return ThesisDecompositionEnvelopeResponse(status=latest.status, message=None, decomposition=latest)


@router.get("/holding/{holding_id}", response_model=list[ThesisResponse])
async def list_theses_for_holding(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.holding_id == holding_id,
            Thesis.user_id == current_user.id,
        )
        .order_by(Thesis.created_at.desc())
    )
    theses = result.scalars().all()
    return theses


@router.get("/current", response_model=list[ThesisResponse])
async def list_current_theses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.user_id == current_user.id,
            Thesis.status.in_(list(CURRENT_THESIS_STATUSES)),
        )
        .order_by(Thesis.created_at.desc())
    )
    theses = result.scalars().all()
    latest_by_holding: dict[uuid.UUID, Thesis] = {}
    for thesis in theses:
        latest_by_holding.setdefault(thesis.holding_id, thesis)
    return list(latest_by_holding.values())


@router.get("/{thesis_id}", response_model=ThesisResponse)
async def get_thesis(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(db, thesis_id=thesis_id, user_id=current_user.id)
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    return thesis


@router.put("/{thesis_id}", response_model=ThesisResponse)
async def update_thesis(
    thesis_id: uuid.UUID,
    body: UpdateThesisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thesis).where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
    )
    thesis = result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    changed_fields: dict[str, str] = {}
    reason_text_changed = False

    if body.thesis_kind is not None:
        thesis.thesis_kind = body.thesis_kind
    if body.why_own_it is not None and body.why_own_it != thesis.why_own_it:
        changed_fields["why_own_it"] = body.why_own_it
        thesis.why_own_it = body.why_own_it
        reason_text_changed = True
    if body.must_remain_true is not None:
        thesis.must_remain_true = body.must_remain_true
    if body.what_would_change_my_mind is not None:
        thesis.what_would_change_my_mind = body.what_would_change_my_mind
    if body.confidence is not None and body.confidence != thesis.confidence:
        changed_fields["confidence"] = body.confidence
        thesis.confidence = body.confidence
    if body.review_cadence_days is not None:
        thesis.review_cadence_days = body.review_cadence_days
    if body.ai_summary is not None:
        thesis.ai_summary = body.ai_summary
    if body.interpretation is not None:
        thesis.interpretation = body.interpretation
    if body.source is not None:
        thesis.source = body.source
    if body.status is not None:
        thesis.status = body.status

    if reason_text_changed:
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=thesis.holding_id,
            user_id=current_user.id,
            entry_type=REASON_UPDATED,
            content=thesis.why_own_it,
            metadata=changed_fields if changed_fields else None,
        )

    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.post("/{thesis_id}/invalidate", response_model=ThesisResponse)
async def invalidate_thesis(
    thesis_id: uuid.UUID,
    body: InvalidateThesisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(db, thesis_id=thesis_id, user_id=current_user.id)
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    thesis.status = "invalidated"
    thesis.invalidated_at = datetime.now(timezone.utc)
    thesis.invalidation_reason = body.reason
    thesis.updated_at = thesis.invalidated_at

    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=thesis.holding_id,
        user_id=current_user.id,
        entry_type=REASON_INVALIDATED,
        content=body.reason or "Thesis invalidated",
    )

    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.post("/{thesis_id}/reaffirm", response_model=ThesisResponse)
async def reaffirm_thesis(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis = await _load_user_thesis(db, thesis_id=thesis_id, user_id=current_user.id)
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.status == "invalidated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalidated theses cannot be reaffirmed")

    thesis.status = "active"
    thesis.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.post("/{thesis_id}/health-check", response_model=HealthCheckResponse)
async def thesis_health_check(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.health_check import run_health_check

    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
        .options(selectinload(Thesis.holding))
    )
    thesis = result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    check = await run_health_check(thesis, thesis.holding)
    return HealthCheckResponse(
        thesis_id=thesis.id,
        ticker=check.ticker,
        current_price=check.current_price,
        currency=thesis.holding.currency or "GBP",
        sector=check.sector,
        pe_ratio=check.pe_ratio,
        market_cap=check.market_cap,
        upcoming_earnings_date=check.upcoming_earnings_date,
        recent_earnings_surprise_pct=check.recent_earnings_surprise_pct,
        candidates=[
            {"event_type": c.event_type, "description": c.description, "severity": c.severity, "ai_analysis": c.ai_analysis}
            for c in check.candidates
        ],
        watch_hints_status=[
            {"metric": w.metric, "operator": w.operator, "threshold": w.threshold, "actual_value": w.actual_value, "breached": w.breached, "rationale": w.rationale}
            for w in check.watch_hints_status
        ],
        recent_news_count=check.recent_news_count,
        thesis_assessment=check.thesis_assessment,
        checked_at=check.checked_at,
    )


@router.post("/{thesis_id}/counter-thesis", response_model=CounterThesisResponse)
async def counter_thesis(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
        .options(selectinload(Thesis.holding))
    )
    thesis = result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    output = await generate_counter_thesis(
        why_own_it=thesis.why_own_it,
        must_remain_true=thesis.must_remain_true,
        what_would_change_my_mind=thesis.what_would_change_my_mind,
        ai_summary=thesis.ai_summary,
        ticker=thesis.holding.ticker,
    )
    return CounterThesisResponse(
        thesis_id=thesis.id,
        bear_case=output.bear_case,
        key_risks=output.key_risks,
        blind_spots=output.blind_spots,
        suggested_additions=output.suggested_additions,
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/{thesis_id}/earnings-review", response_model=EarningsReviewResponse)
async def earnings_review(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.thesis_decomposition import ThesisDecomposition
    from app.services.earnings_review import run_earnings_review
    from app.services.market_data import fetch_company_data

    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
        .options(selectinload(Thesis.holding))
    )
    thesis = result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")
    if thesis.holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    # Load latest confirmed decomposition claims
    decomp_result = await db.execute(
        select(ThesisDecomposition)
        .where(
            ThesisDecomposition.thesis_id == thesis_id,
            ThesisDecomposition.status.in_(["confirmed", "partially_confirmed", "draft"]),
        )
        .options(selectinload(ThesisDecomposition.claims))
        .order_by(ThesisDecomposition.version.desc())
        .limit(1)
    )
    decomp = decomp_result.scalar_one_or_none()
    claims = [
        {"id": str(c.id), "claim_text": c.claim_text}
        for c in (decomp.claims if decomp else [])
    ]

    ticker = thesis.holding.ticker
    company_data = await fetch_company_data(ticker)

    review = await run_earnings_review(
        ticker=ticker,
        name=thesis.holding.name,
        why_own_it=thesis.why_own_it,
        must_remain_true=thesis.must_remain_true,
        what_would_change_my_mind=thesis.what_would_change_my_mind,
        claims=claims,
        company_data=company_data,
    )

    # Persist to conviction log
    metadata = {
        "overall_assessment": review.overall_assessment,
        "fiscal_quarter": review.fiscal_quarter,
        "earnings_surprise_pct": review.earnings_surprise_pct,
        "verdicts": [
            {
                "claim_id": v.claim_id,
                "verdict": v.verdict,
                "evidence": v.evidence,
            }
            for v in review.verdicts
        ],
    }
    log_entry = append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=thesis.holding_id,
        user_id=current_user.id,
        entry_type=POST_EARNINGS_REVIEW,
        content=review.summary,
        metadata=metadata,
    )
    await db.flush()
    await db.commit()
    await db.refresh(log_entry)

    reviewed_at = datetime.now(timezone.utc)
    return EarningsReviewResponse(
        thesis_id=thesis.id,
        ticker=ticker,
        verdicts=[
            ClaimVerdictResponse(
                claim_id=v.claim_id,
                claim_text=v.claim_text,
                verdict=v.verdict,
                explanation=v.explanation,
                evidence=v.evidence,
            )
            for v in review.verdicts
        ],
        overall_assessment=review.overall_assessment,
        summary=review.summary,
        fiscal_quarter=review.fiscal_quarter,
        earnings_surprise_pct=review.earnings_surprise_pct,
        log_entry_id=log_entry.id,
        reviewed_at=reviewed_at,
    )


@router.get("/{thesis_id}/health-history")
async def get_health_history(
    thesis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.thesis_health_snapshot import ThesisHealthSnapshot
    result = await db.execute(
        select(Thesis)
        .where(Thesis.id == thesis_id, Thesis.user_id == user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Thesis not found")

    snaps = await db.execute(
        select(ThesisHealthSnapshot)
        .where(ThesisHealthSnapshot.thesis_id == thesis_id)
        .order_by(ThesisHealthSnapshot.computed_at.asc())
        .limit(90)
    )
    return [
        {"score": s.score, "label": s.label, "computed_at": s.computed_at.isoformat()}
        for s in snaps.scalars().all()
    ]
