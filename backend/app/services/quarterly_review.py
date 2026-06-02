from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


def _normalize_datetime(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def current_quarter_key(now: datetime | None = None) -> str:
    reference = now or datetime.now(timezone.utc)
    quarter = ((reference.month - 1) // 3) + 1
    return f"{reference.year}-Q{quarter}"


def quarterly_review_release_at(now: datetime | None = None) -> datetime:
    reference = now or datetime.now(timezone.utc)
    quarter_start_month = (((reference.month - 1) // 3) * 3) + 1
    release = datetime(reference.year, quarter_start_month, 1, 8, 0, 0, tzinfo=timezone.utc)
    while release.weekday() != 0:
        release += timedelta(days=1)
    return release


def is_quarterly_review_open(now: datetime | None = None) -> bool:
    reference = now or datetime.now(timezone.utc)
    return reference >= quarterly_review_release_at(reference)


def _age_in_days(timestamp: datetime, *, now: datetime) -> int:
    return (_normalize_datetime(now) - _normalize_datetime(timestamp)).days


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


async def _load_current_holdings(db: AsyncSession, *, user_id: uuid.UUID) -> list[Holding]:
    holdings_result = await db.execute(
        select(Holding)
        .where(Holding.user_id == user_id)
        .order_by(Holding.current_value.desc().nulls_last(), Holding.ticker.asc())
    )
    return list(holdings_result.scalars().all())


async def _load_current_theses_by_holding(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Thesis]:
    if not holding_ids:
        return {}

    theses_result = await db.execute(
        select(Thesis)
        .where(
            Thesis.user_id == user_id,
            Thesis.holding_id.in_(holding_ids),
            Thesis.status.in_(list(ACTIVE_THESIS_STATUSES)),
        )
        .order_by(Thesis.created_at.desc())
    )
    theses = theses_result.scalars().all()

    current_thesis_by_holding: dict[uuid.UUID, Thesis] = {}
    for thesis in theses:
        current_thesis_by_holding.setdefault(thesis.holding_id, thesis)
    return current_thesis_by_holding


async def _load_responses_by_holding(
    db: AsyncSession,
    *,
    review_id: uuid.UUID,
) -> dict[uuid.UUID, QuarterlyReviewResponse]:
    responses_result = await db.execute(
        select(QuarterlyReviewResponse).where(QuarterlyReviewResponse.review_id == review_id)
    )
    responses = responses_result.scalars().all()
    return {response.holding_id: response for response in responses}


def _build_review_items(
    *,
    holdings: list[Holding],
    thesis_by_holding: dict[uuid.UUID, Thesis],
    response_by_holding: dict[uuid.UUID, QuarterlyReviewResponse],
    now: datetime,
) -> list[QuarterlyReviewHoldingItem]:
    items: list[QuarterlyReviewHoldingItem] = []
    for holding in holdings:
        thesis = thesis_by_holding.get(holding.id)
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
                reason_age_days=_age_in_days(thesis.created_at, now=now),
                why_own_it=thesis.why_own_it,
                response=response.response if response is not None else None,
                response_notes=response.notes if response is not None else None,
                reviewed_at=response.created_at if response is not None else None,
            )
        )
    return items


def _pending_count(items: list[QuarterlyReviewHoldingItem]) -> int:
    return sum(1 for item in items if item.response is None)


def _update_review_status(review: QuarterlyReview, items: list[QuarterlyReviewHoldingItem]) -> None:
    review.status = "completed" if not items or _pending_count(items) == 0 else "pending"


def _apply_thesis_status_transition(*, thesis: Thesis, response_value: str) -> None:
    if response_value in {"yes_absolutely", "probably"} and thesis.status == "needs_review":
        thesis.status = "active"
    elif response_value in {"not_sure", "no"} and thesis.status in {"active", "draft"}:
        thesis.status = "needs_review"


async def get_or_create_current_review(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> QuarterlyReview:
    quarter = current_quarter_key(now)
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
    db: AsyncSession, *, user_id: uuid.UUID, now: datetime | None = None
) -> tuple[QuarterlyReview, list[QuarterlyReviewHoldingItem]]:
    reference_now = now or datetime.now(timezone.utc)
    review = await get_or_create_current_review(db, user_id=user_id, now=reference_now)
    holdings = await _load_current_holdings(db, user_id=user_id)
    holding_ids = [holding.id for holding in holdings]
    current_thesis_by_holding = await _load_current_theses_by_holding(
        db,
        user_id=user_id,
        holding_ids=holding_ids,
    )
    response_by_holding = await _load_responses_by_holding(db, review_id=review.id)
    items = _build_review_items(
        holdings=holdings,
        thesis_by_holding=current_thesis_by_holding,
        response_by_holding=response_by_holding,
        now=reference_now,
    )
    _update_review_status(review, items)
    await db.flush()
    return review, items


async def submit_quarterly_review_response(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    response_value: str,
    notes: str | None = None,
    now: datetime | None = None,
) -> tuple[QuarterlyReviewResponse, Thesis, int]:
    if response_value not in VALID_RESPONSES:
        raise ValueError("Invalid quarterly review response")

    reference_now = now or datetime.now(timezone.utc)
    review, items = await build_current_review_snapshot(db, user_id=user_id, now=reference_now)
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
        review_response.created_at = reference_now

    _apply_thesis_status_transition(thesis=thesis, response_value=response_value)

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

    # Decision-mirror capture: a quarterly re-underwrite is a conviction call too.
    from app.services.decision_snapshots import capture_quarterly_decision

    await capture_quarterly_decision(
        db, thesis=thesis, holding=holding, response_value=response_value, notes=notes
    )

    pending_count = max(_pending_count(items) - (1 if item.response is None else 0), 0)
    review.status = "completed" if pending_count == 0 else "pending"
    await db.flush()
    return review_response, thesis, pending_count
