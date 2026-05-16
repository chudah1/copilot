from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.quarterly_review import QuarterlyReview
from app.models.quarterly_review_response import QuarterlyReviewResponse
from app.models.thesis import Thesis
from app.services.conviction_log import QUARTERLY_REVIEW, append_log_entry

VALID_RESPONSES = {"yes_absolutely", "probably", "not_sure", "no"}
ACTIVE_THESIS_STATUSES = {"draft", "active", "needs_review"}


@dataclass
class QuarterlyReviewHoldingItem:
    holding_id: uuid.UUID
    thesis_id: uuid.UUID
    ticker: str
    name: str
    currency: str
    current_price: float | None
    reason_age_days: int
    why_own_it: str
    response: str | None
    response_notes: str | None
    reviewed_at: datetime | None


def current_quarter_key(now: datetime | None = None) -> str:
    reference = now or datetime.now(timezone.utc)
    quarter = ((reference.month - 1) // 3) + 1
    return f"{reference.year}-Q{quarter}"


def _age_in_days(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - normalized).days


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _resolve_price(holding: Holding) -> float | None:
    if holding.current_price is not None:
        return _to_float(holding.current_price)
    if holding.average_cost_basis is not None:
        return _to_float(holding.average_cost_basis)
    return None


def _response_label(response: str) -> str:
    return response.replace("_", " ")


async def get_or_create_current_review(db: AsyncSession, *, user_id: uuid.UUID) -> QuarterlyReview:
    quarter = current_quarter_key()
    result = await db.execute(
        select(QuarterlyReview).where(
            QuarterlyReview.user_id == user_id,
            QuarterlyReview.quarter == quarter,
        )
    )
    review = result.scalar_one_or_none()
    if review is not None:
        return review

    review = QuarterlyReview(user_id=user_id, quarter=quarter, status="pending")
    db.add(review)
    await db.flush()
    return review


async def build_current_review_snapshot(
    db: AsyncSession, *, user_id: uuid.UUID
) -> tuple[QuarterlyReview, list[QuarterlyReviewHoldingItem]]:
    review = await get_or_create_current_review(db, user_id=user_id)

    holdings_result = await db.execute(
        select(Holding)
        .where(Holding.user_id == user_id)
        .order_by(Holding.current_value.desc().nulls_last(), Holding.ticker.asc())
    )
    holdings = holdings_result.scalars().all()

    theses_result = await db.execute(
        select(Thesis)
        .where(
            Thesis.user_id == user_id,
            Thesis.status.in_(list(ACTIVE_THESIS_STATUSES)),
        )
        .order_by(Thesis.created_at.desc())
    )
    theses = theses_result.scalars().all()

    current_thesis_by_holding: dict[uuid.UUID, Thesis] = {}
    for thesis in theses:
        current_thesis_by_holding.setdefault(thesis.holding_id, thesis)

    responses_result = await db.execute(
        select(QuarterlyReviewResponse).where(QuarterlyReviewResponse.review_id == review.id)
    )
    responses = responses_result.scalars().all()
    response_by_holding = {response.holding_id: response for response in responses}

    items: list[QuarterlyReviewHoldingItem] = []
    for holding in holdings:
        thesis = current_thesis_by_holding.get(holding.id)
        if thesis is None:
            continue
        response = response_by_holding.get(holding.id)
        items.append(
            QuarterlyReviewHoldingItem(
                holding_id=holding.id,
                thesis_id=thesis.id,
                ticker=holding.ticker,
                name=holding.name,
                currency=holding.currency,
                current_price=_resolve_price(holding),
                reason_age_days=_age_in_days(thesis.created_at),
                why_own_it=thesis.why_own_it,
                response=response.response if response is not None else None,
                response_notes=response.notes if response is not None else None,
                reviewed_at=response.created_at if response is not None else None,
            )
        )

    completed_count = sum(1 for item in items if item.response is not None)
    review.status = "completed" if not items or completed_count == len(items) else "pending"
    await db.flush()
    return review, items


async def submit_quarterly_review_response(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    response_value: str,
    notes: str | None = None,
) -> tuple[QuarterlyReviewResponse, Thesis, int]:
    if response_value not in VALID_RESPONSES:
        raise ValueError("Invalid quarterly review response")

    review, items = await build_current_review_snapshot(db, user_id=user_id)
    item_by_holding = {item.holding_id: item for item in items}
    item = item_by_holding.get(holding_id)
    if item is None:
        raise ValueError("Holding is not eligible for the current quarterly review")

    holding_result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id)
    )
    holding = holding_result.scalar_one_or_none()
    if holding is None:
        raise ValueError("Holding not found")

    thesis_result = await db.execute(
        select(Thesis).where(Thesis.id == item.thesis_id, Thesis.user_id == user_id)
    )
    thesis = thesis_result.scalar_one_or_none()
    if thesis is None:
        raise ValueError("Thesis not found")

    response_result = await db.execute(
        select(QuarterlyReviewResponse).where(
            QuarterlyReviewResponse.review_id == review.id,
            QuarterlyReviewResponse.holding_id == holding_id,
        )
    )
    review_response = response_result.scalar_one_or_none()
    if review_response is None:
        review_response = QuarterlyReviewResponse(
            review_id=review.id,
            holding_id=holding_id,
            thesis_id=thesis.id,
            response=response_value,
            price_at_review=_resolve_price(holding),
            notes=notes,
        )
        db.add(review_response)
    else:
        review_response.thesis_id = thesis.id
        review_response.response = response_value
        review_response.price_at_review = _resolve_price(holding)
        review_response.notes = notes
        review_response.created_at = datetime.now(timezone.utc)

    if response_value in {"yes_absolutely", "probably"} and thesis.status == "needs_review":
        thesis.status = "active"
    elif response_value in {"not_sure", "no"} and thesis.status in {"active", "draft"}:
        thesis.status = "needs_review"

    price_text = (
        f"{holding.currency} {review_response.price_at_review:,.2f}"
        if review_response.price_at_review is not None
        else "the current price"
    )
    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=user_id,
        entry_type=QUARTERLY_REVIEW,
        content=f"Quarterly review: {_response_label(response_value)} at {price_text}.",
        metadata={
            "quarter": review.quarter,
            "response": response_value,
            "price_at_review": review_response.price_at_review,
            "notes": notes,
        },
    )

    await db.flush()
    _, refreshed_items = await build_current_review_snapshot(db, user_id=user_id)
    pending_count = sum(1 for item in refreshed_items if item.response is None)
    return review_response, thesis, pending_count
