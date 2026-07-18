from datetime import datetime, timezone

from sqlalchemy import select

from app.jobs.quarterly_review_prep import run_quarterly_review_prep
from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.holding import Holding
from app.models.quarterly_review import QuarterlyReview
from app.models.quarterly_review_response import QuarterlyReviewResponse
from app.models.thesis import Thesis
from app.services.conviction_log import QUARTERLY_REVIEW
from app.services.quarterly_review import (
    build_current_review_snapshot,
    current_quarter_key,
    is_quarterly_review_open,
    quarterly_review_release_at,
    submit_quarterly_review_response,
)


async def _create_holding(db, user, *, ticker: str, price: float = 150.0):
    holding = Holding(
        user_id=user.id,
        ticker=ticker,
        name=ticker,
        quantity=10,
        average_cost_basis=100,
        current_price=price,
        current_value=price * 10,
        currency="GBP",
    )
    db.add(holding)
    await db.flush()
    return holding


async def _create_thesis(
    db,
    user,
    holding,
    *,
    status: str = "active",
    why_own_it: str | None = None,
    created_at: datetime | None = None,
):
    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status=status,
        thesis_kind="company",
        why_own_it=why_own_it or f"I own {holding.ticker} because it compounds well.",
        confidence="high",
        review_cadence_days=30,
        source="user",
        created_at=created_at or datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    db.add(thesis)
    await db.flush()
    return thesis


async def test_get_current_quarterly_review_returns_pending_holdings(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user, ticker="AAPL")
    thesis = await _create_thesis(db, test_user, holding, why_own_it="Apple compounds through its ecosystem.")
    await db.commit()

    response = await client.get("/api/quarterly-review/current", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["quarter"] == current_quarter_key()
    assert data["status"] == "pending"
    assert data["total_holdings"] == 1
    assert data["completed_count"] == 0
    assert data["pending_count"] == 1
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["holding_id"] == str(holding.id)
    assert data["holdings"][0]["thesis_id"] == str(thesis.id)
    assert data["holdings"][0]["why_own_it"] == "Apple compounds through its ecosystem."


async def test_quarterly_review_response_marks_review_completed_and_logs(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user, ticker="ASML", price=743.0)
    thesis = await _create_thesis(db, test_user, holding)
    await db.commit()

    response = await client.post(
        "/api/quarterly-review/current/respond",
        json={
            "holding_id": str(holding.id),
            "response": "not_sure",
            "notes": "Margins feel less predictable now.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["holding_id"] == str(holding.id)
    assert data["thesis_id"] == str(thesis.id)
    assert data["response"] == "not_sure"
    assert data["pending_count"] == 0
    assert data["thesis_status"] == "needs_review"

    review_result = await db.execute(select(QuarterlyReview))
    review = review_result.scalar_one()
    assert review.quarter == current_quarter_key()
    assert review.status == "completed"

    response_result = await db.execute(
        select(QuarterlyReviewResponse).where(QuarterlyReviewResponse.holding_id == holding.id)
    )
    review_response = response_result.scalar_one()
    assert review_response.notes == "Margins feel less predictable now."
    assert review_response.price_at_review == 743.0

    log_result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.holding_id == holding.id,
            ConvictionLogEntry.entry_type == QUARTERLY_REVIEW,
        )
    )
    log_entry = log_result.scalar_one()
    assert log_entry.metadata_json["response"] == "not_sure"
    assert log_entry.metadata_json["notes"] == "Margins feel less predictable now."


async def test_positive_quarterly_review_reactivates_needs_review_thesis(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user, ticker="SHOP", price=92.5)
    thesis = await _create_thesis(db, test_user, holding, status="needs_review")
    await db.commit()

    response = await client.post(
        "/api/quarterly-review/current/respond",
        json={
            "holding_id": str(holding.id),
            "response": "yes_absolutely",
            "notes": "Still one of the clearest reasons in the portfolio.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["thesis_status"] == "active"

    await db.refresh(thesis)
    assert thesis.status == "active"


def test_quarterly_review_release_window_opens_on_first_monday():
    before_release = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc)
    release_day = datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc)

    assert quarterly_review_release_at(before_release) == datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)
    assert is_quarterly_review_open(before_release) is False
    assert is_quarterly_review_open(release_day) is True


async def test_quarterly_review_prep_job_creates_current_review(db, test_user, job_session_factory):
    holding = await _create_holding(db, test_user, ticker="NVDA", price=880.0)
    await _create_thesis(db, test_user, holding)
    await db.commit()

    await run_quarterly_review_prep(
        now=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
        session_factory=job_session_factory,
    )

    result = await db.execute(select(QuarterlyReview).where(QuarterlyReview.user_id == test_user.id))
    review = result.scalar_one()
    assert review.quarter == "2026-Q2"


async def test_build_current_review_snapshot_uses_reference_now_for_reason_age(db, test_user):
    holding = await _create_holding(db, test_user, ticker="META", price=500.0)
    thesis = await _create_thesis(db, test_user, holding)
    thesis.created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    await db.commit()

    _, items = await build_current_review_snapshot(
        db,
        user_id=test_user.id,
        now=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
    )

    assert len(items) == 1
    assert items[0].reason_age_days == 90


async def test_current_quarter_position_is_not_immediately_due_for_quarterly_review(db, test_user):
    holding = await _create_holding(db, test_user, ticker="NOW", price=900.0)
    await _create_thesis(
        db,
        test_user,
        holding,
        created_at=datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc),
    )
    await db.commit()

    review, items = await build_current_review_snapshot(
        db,
        user_id=test_user.id,
        now=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )

    assert review.quarter == "2026-Q3"
    assert items == []
    assert review.status == "completed"

    next_review, next_items = await build_current_review_snapshot(
        db,
        user_id=test_user.id,
        now=datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc),
    )

    assert next_review.quarter == "2026-Q4"
    assert [item.ticker for item in next_items] == ["NOW"]
    assert next_review.status == "pending"


async def test_submit_quarterly_review_response_reuses_existing_row_and_updates_status(db, test_user):
    holding = await _create_holding(db, test_user, ticker="ADBE", price=410.0)
    thesis = await _create_thesis(db, test_user, holding, status="needs_review")
    await db.commit()

    first_response, _, pending_count = await submit_quarterly_review_response(
        db,
        user_id=test_user.id,
        holding_id=holding.id,
        response_value="not_sure",
        notes="Unsure on demand quality.",
        now=datetime(2026, 4, 10, 9, 0, tzinfo=timezone.utc),
    )
    assert pending_count == 0

    second_response, thesis, pending_count = await submit_quarterly_review_response(
        db,
        user_id=test_user.id,
        holding_id=holding.id,
        response_value="probably",
        notes="Still looks good enough.",
        now=datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc),
    )
    await db.flush()

    responses = (
        await db.execute(select(QuarterlyReviewResponse).where(QuarterlyReviewResponse.holding_id == holding.id))
    ).scalars().all()
    assert len(responses) == 1
    assert first_response.id == second_response.id
    assert second_response.created_at == datetime(2026, 4, 12, 9, 0, tzinfo=timezone.utc)
    assert thesis.status == "active"
    assert pending_count == 0
