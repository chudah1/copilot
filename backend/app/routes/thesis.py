import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.thesis import GenerateThesisRequest, ThesisResponse, UpdateThesisRequest, InvalidateThesisRequest
from app.services.ai_thesis import generate_thesis

router = APIRouter(prefix="/api/theses", tags=["theses"])


@router.post("/generate", response_model=ThesisResponse, status_code=status.HTTP_201_CREATED)
async def generate_thesis_endpoint(
    body: GenerateThesisRequest,
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

    output = await generate_thesis(
        ticker=holding.ticker,
        name=holding.name,
        quantity=float(holding.quantity),
        average_cost=float(holding.average_cost_basis),
    )

    if output is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate thesis — try again or write manually",
        )

    thesis = Thesis(
        holding_id=holding.id,
        user_id=current_user.id,
        status="draft",
        bull_case=output.bull_case,
        key_metrics=output.key_metrics,
        risk_factors=output.risk_factors,
        conviction=output.suggested_conviction,
        ai_generated=True,
    )
    db.add(thesis)
    await db.commit()
    await db.refresh(thesis)
    return thesis


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

    if body.bull_case is not None:
        thesis.bull_case = body.bull_case
    if body.key_metrics is not None:
        thesis.key_metrics = [m.model_dump() for m in body.key_metrics]
    if body.risk_factors is not None:
        thesis.risk_factors = body.risk_factors
    if body.conviction is not None:
        thesis.conviction = body.conviction
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
