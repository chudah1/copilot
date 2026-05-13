import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
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
    CreateThesisRequest,
    InvalidateThesisRequest,
    ThesisDecompositionEnvelopeResponse,
    ThesisDecompositionResponse,
    ThesisResponse,
    UpdateThesisRequest,
)
from app.services.ai_thesis import assist_thesis
from app.services.decomposition import PersistedDecompositionResult, generate_decomposition_for_thesis

router = APIRouter(prefix="/api/theses", tags=["theses"])


CURRENT_THESIS_STATUSES = {"draft", "active", "needs_review"}


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


def _decomposition_envelope_from_result(result: PersistedDecompositionResult) -> ThesisDecompositionEnvelopeResponse:
    return ThesisDecompositionEnvelopeResponse(
        status=result.status,
        message=result.message,
        decomposition=result.decomposition,
    )


@router.post("", response_model=ThesisResponse, status_code=status.HTTP_201_CREATED)
async def create_thesis(
    body: CreateThesisRequest,
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
    await db.commit()
    await db.refresh(thesis)
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
    )
    if output is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to assist thesis draft")
    return AssistThesisResponse(ai_summary=output.ai_summary, interpretation=output.interpretation)


@router.post("/{thesis_id}/decompose", response_model=ThesisDecompositionEnvelopeResponse, status_code=status.HTTP_201_CREATED)
async def decompose_thesis(
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

    result = await generate_decomposition_for_thesis(db=db, thesis=thesis, holding=thesis.holding)
    if result.status == "pending":
        envelope = _decomposition_envelope_from_result(result)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=envelope.model_dump(mode="json"),
        )
    if result.status == "failed":
        envelope = _decomposition_envelope_from_result(result)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=envelope.model_dump(mode="json"),
        )
    latest = await _get_latest_decomposition_record(db, thesis.id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create decomposition")
    return ThesisDecompositionEnvelopeResponse(status="draft", message=None, decomposition=latest)


@router.get("/{thesis_id}/decomposition", response_model=ThesisDecompositionEnvelopeResponse)
async def get_latest_decomposition(
    thesis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thesis_result = await db.execute(
        select(Thesis).where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
    )
    thesis = thesis_result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    latest = await _get_latest_decomposition_record(db, thesis_id, current_user.id)
    if latest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decomposition not found")
    if latest.status != "draft":
        message = "We saved your thesis and are retrying decomposition." if latest.status == "pending" else latest.last_error
        return ThesisDecompositionEnvelopeResponse(status=latest.status, message=message, decomposition=None)
    return ThesisDecompositionEnvelopeResponse(status="draft", message=None, decomposition=latest)


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
    result = await db.execute(
        select(Thesis).where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
    )
    thesis = result.scalar_one_or_none()
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

    if body.thesis_kind is not None:
        thesis.thesis_kind = body.thesis_kind
    if body.why_own_it is not None:
        thesis.why_own_it = body.why_own_it
    if body.must_remain_true is not None:
        thesis.must_remain_true = body.must_remain_true
    if body.what_would_change_my_mind is not None:
        thesis.what_would_change_my_mind = body.what_would_change_my_mind
    if body.confidence is not None:
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
    result = await db.execute(
        select(Thesis).where(
            Thesis.id == thesis_id,
            Thesis.user_id == current_user.id,
        )
    )
    thesis = result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thesis not found")

    thesis.status = "invalidated"
    thesis.invalidated_at = datetime.now(timezone.utc)
    thesis.invalidation_reason = body.reason

    await db.commit()
    await db.refresh(thesis)
    return thesis


@router.post("/{thesis_id}/reaffirm", response_model=ThesisResponse)
async def reaffirm_thesis(
    thesis_id: uuid.UUID,
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
    if thesis.status == "invalidated":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalidated theses cannot be reaffirmed")

    thesis.status = "active"
    thesis.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thesis)
    return thesis
