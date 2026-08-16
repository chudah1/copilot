from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.quarterly_review import (
    DecisionPatternsResponse,
    QuarterlyReviewCurrentResponse,
    QuarterlyReviewHoldingResponse,
    QuarterlyReviewSubmissionResponse,
    SubmitQuarterlyReviewRequest,
)
from app.services.quarterly_review import (
    build_current_review_snapshot,
    submit_quarterly_review_response,
)

router = APIRouter(prefix="/api/quarterly-review", tags=["quarterly-review"])


@router.get("/patterns", response_model=DecisionPatternsResponse)
async def get_decision_patterns_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate behavioural patterns across the user's resolved conviction calls
    — the quarterly reckoning surface of the decision mirror."""
    from app.services.decision_mirror import get_decision_patterns

    return await get_decision_patterns(db, user.id)


@router.get("/current", response_model=QuarterlyReviewCurrentResponse)
async def get_current_review(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review, items = await build_current_review_snapshot(db, user_id=user.id)
    await db.commit()
    completed_count = sum(1 for item in items if item.response is not None)
    return QuarterlyReviewCurrentResponse(
        review_id=review.id,
        quarter=review.quarter,
        status=review.status,
        total_holdings=len(items),
        completed_count=completed_count,
        pending_count=len(items) - completed_count,
        holdings=[
            QuarterlyReviewHoldingResponse(
                holding_id=item.holding_id,
                thesis_id=item.thesis_id,
                ticker=item.ticker,
                name=item.name,
                currency=item.currency,
                current_price=item.current_price,
                reason_age_days=item.reason_age_days,
                why_own_it=item.why_own_it,
                response=item.response,
                response_notes=item.response_notes,
                reviewed_at=item.reviewed_at,
            )
            for item in items
        ],
    )


@router.post("/current/respond", response_model=QuarterlyReviewSubmissionResponse)
async def respond_to_current_review(
    body: SubmitQuarterlyReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        review_response, thesis, pending_count = await submit_quarterly_review_response(
            db,
            user_id=user.id,
            holding_id=body.holding_id,
            response_value=body.response,
            notes=body.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "Holding is not eligible for the current quarterly review":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    await db.commit()
    await db.refresh(review_response)
    await db.refresh(thesis)

    return QuarterlyReviewSubmissionResponse(
        review_id=review_response.review_id,
        holding_id=review_response.holding_id,
        thesis_id=review_response.thesis_id,
        response=review_response.response,
        notes=review_response.notes,
        price_at_review=review_response.price_at_review,
        created_at=review_response.created_at,
        thesis_status=thesis.status,
        pending_count=pending_count,
    )
