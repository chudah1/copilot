import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.quarterly_review import QuarterlyReview
from app.models.quarterly_review_response import QuarterlyReviewResponse
from app.models.thesis import Thesis


@pytest.mark.asyncio
async def test_open_loops_endpoint_derives_claim_review_and_review_overdue_loops(
    client, auth_headers, db, test_user
):
    review_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=3,
        average_cost_basis=120,
        current_value=900,
        currency="USD",
    )
    overdue_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="MSFT",
        name="Microsoft",
        quantity=4,
        average_cost_basis=200,
        current_value=1200,
        currency="USD",
    )
    db.add_all([review_holding, overdue_holding])
    await db.flush()

    review_thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=review_holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI demand remains strong.",
        must_remain_true="Inference demand holds up.",
        what_would_change_my_mind="GPU demand weakens.",
        confidence="high",
        review_cadence_days=30,
        source="user",
    )
    overdue_thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=overdue_holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Cloud and AI continue compounding.",
        must_remain_true="Enterprise demand stays intact.",
        what_would_change_my_mind="Cloud growth stalls materially.",
        confidence="high",
        review_cadence_days=14,
        updated_at=datetime.now(timezone.utc) - timedelta(days=140),
        source="user",
        interpretation={"monitorability": "high"},
    )
    db.add_all([review_thesis, overdue_thesis])
    await db.flush()

    db.add(
        MonitoringEvent(
            id=uuid.uuid4(),
            holding_id=review_holding.id,
            thesis_id=review_thesis.id,
            event_type="news_or_earnings_candidate",
            severity="thesis_breaking",
            verdict="threatens",
            title="AI demand softens",
            summary="Orders slowed materially this quarter.",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    await db.commit()

    response = await client.get("/api/dashboard/open-loops", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    loop_types = {item["loop_type"] for item in data}
    assert "claim_review" in loop_types
    assert "review_overdue" in loop_types
    assert data[0]["ticker"] == "NVDA"
    assert data[0]["cta_href"].endswith("?tab=monitoring")


@pytest.mark.asyncio
async def test_open_loops_endpoint_derives_quarterly_uncertainty_loop(
    client, auth_headers, db, test_user
):
    holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="TSLA",
        name="Tesla",
        quantity=5,
        average_cost_basis=220,
        current_value=1000,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=holding.id,
        status="needs_review",
        thesis_kind="company",
        why_own_it="Scale and energy storage keep compounding.",
        must_remain_true="Auto margins recover.",
        what_would_change_my_mind="Demand stays weak for multiple quarters.",
        confidence="medium",
        review_cadence_days=30,
        source="user",
        interpretation={"monitorability": "high"},
    )
    db.add(thesis)
    await db.flush()

    review = QuarterlyReview(
        id=uuid.uuid4(),
        user_id=test_user.id,
        quarter="2026-Q3",
        status="pending",
    )
    db.add(review)
    await db.flush()

    db.add(
        QuarterlyReviewResponse(
            id=uuid.uuid4(),
            review_id=review.id,
            holding_id=holding.id,
            thesis_id=thesis.id,
            response="not_sure",
            notes="Need another pass on the growth story.",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
    )
    await db.commit()

    response = await client.get("/api/dashboard/open-loops", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    quarterly_loop = next(item for item in data if item["loop_type"] == "quarterly_unsure")
    assert quarterly_loop["ticker"] == "TSLA"
    assert quarterly_loop["cta_label"] == "Resolve quarterly call"


@pytest.mark.asyncio
async def test_dismissing_open_loop_hides_it_until_expiry(
    client, auth_headers, db, test_user
):
    holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="SHOP",
        name="Shopify",
        quantity=6,
        average_cost_basis=80,
        current_value=1000,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Growth.",
        confidence="medium",
        review_cadence_days=30,
        source="user",
        interpretation={"monitorability": "low", "ambiguity_note": "Too vague to monitor."},
    )
    db.add(thesis)
    await db.commit()

    open_response = await client.get("/api/dashboard/open-loops", headers=auth_headers)
    assert open_response.status_code == 200
    loops = open_response.json()
    weak_loop = next(item for item in loops if item["loop_type"] == "weak_thesis")

    dismiss_response = await client.post(
        "/api/dashboard/open-loops/dismiss",
        headers=auth_headers,
        json={"loop_key": weak_loop["loop_key"], "dismiss_for_days": 7},
    )
    assert dismiss_response.status_code == 200

    refreshed = await client.get("/api/dashboard/open-loops", headers=auth_headers)
    assert refreshed.status_code == 200
    refreshed_keys = {item["loop_key"] for item in refreshed.json()}
    assert weak_loop["loop_key"] not in refreshed_keys


@pytest.mark.asyncio
async def test_open_loops_endpoint_can_filter_to_single_holding(
    client, auth_headers, db, test_user
):
    first_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="AMD",
        name="AMD",
        quantity=5,
        average_cost_basis=100,
        current_value=800,
        currency="USD",
    )
    second_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="UBER",
        name="Uber",
        quantity=8,
        average_cost_basis=50,
        current_value=600,
        currency="USD",
    )
    db.add_all([first_holding, second_holding])
    await db.flush()

    db.add_all([
        Thesis(
            id=uuid.uuid4(),
            user_id=test_user.id,
            holding_id=first_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Growth.",
            confidence="medium",
            review_cadence_days=30,
            source="user",
            interpretation={"monitorability": "low", "ambiguity_note": "Too vague to monitor."},
        ),
        Thesis(
            id=uuid.uuid4(),
            user_id=test_user.id,
            holding_id=second_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Mobility demand keeps compounding.",
            must_remain_true="Bookings growth stays healthy.",
            what_would_change_my_mind="Demand softens materially.",
            confidence="high",
            review_cadence_days=14,
            updated_at=datetime.now(timezone.utc) - timedelta(days=140),
            source="user",
            interpretation={"monitorability": "high"},
        ),
    ])
    await db.commit()

    response = await client.get(
        f"/api/dashboard/open-loops?holding_id={first_holding.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "AMD"
