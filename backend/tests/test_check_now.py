import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.market_data import CompanyData


def _make_company_data(ticker="AAPL", current_price=120.0):
    return CompanyData(
        ticker=ticker,
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=current_price,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )


async def test_check_now_creates_monitoring_events(client, auth_headers, db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        must_remain_true="Revenue keeps growing.",
        what_would_change_my_mind="A major revenue miss.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Large moves."}
            ]
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(current_price=120.0)
    classification = type(
        "Classification", (), {"severity": "warning", "analysis": "Price moved."}
    )()

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ):
        with patch(
            "app.services.check_now.classify_event",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            response = await client.post(
                f"/api/monitoring/holdings/{holding.id}/check-now",
                headers=auth_headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["events_created"] >= 1

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(events) >= 1


async def test_check_now_rate_limited_when_recent_event_exists(client, auth_headers, db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        confidence="high",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    # Create a recent event (within the 4-hour window)
    recent_event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="Review AAPL",
        summary="Price moved significantly.",
    )
    db.add(recent_event)
    await db.commit()

    response = await client.post(
        f"/api/monitoring/holdings/{holding.id}/check-now",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rate_limited"
    assert data["events_created"] == 0
    assert data["next_available_at"] is not None


async def test_check_now_returns_400_when_no_thesis(client, auth_headers, db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.commit()

    response = await client.post(
        f"/api/monitoring/holdings/{holding.id}/check-now",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No active thesis"


async def test_check_now_requires_auth(client, db):
    fake_id = uuid.uuid4()
    response = await client.post(f"/api/monitoring/holdings/{fake_id}/check-now")
    assert response.status_code in (401, 403)
