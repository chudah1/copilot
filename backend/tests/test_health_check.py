import uuid
from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.health_check import HealthCheckResult, run_health_check
from app.services.market_data import CompanyData


def _make_company_data(ticker: str = "AAPL", price: float = 195.0) -> CompanyData:
    return CompanyData(
        ticker=ticker,
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=price,
        market_cap=3_000_000_000_000.0,
        pe_ratio=30.5,
        revenue_growth_yoy=0.04,
        earnings_growth_yoy=0.08,
        dividend_yield=0.005,
        description="Apple Inc.",
        recent_news=["Apple launches new AI features"],
        upcoming_earnings_date=datetime(2026, 7, 24, tzinfo=timezone.utc),
        recent_earnings_surprise_pct=2.5,
        news_items=[],
        recent_fiscal_quarter="2026Q1",
        earnings_call=None,
        insider_transactions=[],
        provider_payload={},
    )


@pytest.mark.asyncio
@patch("app.services.health_check.fetch_company_data")
@patch("app.services.health_check.classify_event")
async def test_health_check_returns_structured_result(mock_classify, mock_fetch):
    mock_fetch.return_value = _make_company_data()
    mock_classify.return_value = None  # No AI classification

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        current_price=190.0, user_id=uuid.uuid4(),
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=holding.user_id,
        status="active", why_own_it="AI hardware play",
        must_remain_true="Revenue keeps growing",
        what_would_change_my_mind="Growth stalls",
        confidence="medium", interpretation={
            "watch_hints": [
                {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Must grow"},
            ]
        },
    )

    result = await run_health_check(thesis, holding)

    assert isinstance(result, HealthCheckResult)
    assert result.ticker == "AAPL"
    assert result.current_price == 195.0
    assert result.sector == "Technology"
    assert result.thesis_assessment in ("all_clear", "watch", "review_needed")
    assert result.checked_at is not None


@pytest.mark.asyncio
@patch("app.services.health_check.fetch_company_data")
async def test_health_check_graceful_on_fetch_failure(mock_fetch):
    mock_fetch.side_effect = Exception("API down")

    holding = Holding(
        id=uuid.uuid4(), ticker="FAIL", name="FailCorp",
        quantity=10, average_cost_basis=50, currency="GBP",
        user_id=uuid.uuid4(),
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=holding.user_id,
        status="active", why_own_it="Testing", confidence="low",
    )

    result = await run_health_check(thesis, holding)

    assert result.ticker == "FAIL"
    assert result.current_price is None
    assert result.candidates == []
    assert result.thesis_assessment == "all_clear"


@pytest.mark.asyncio
@patch("app.services.health_check.fetch_company_data")
@patch("app.services.health_check.classify_event")
async def test_health_check_detects_breached_watch_hint(mock_classify, mock_fetch):
    cd = _make_company_data()
    cd.revenue_growth_yoy = -0.05  # Negative growth — breaches >= 0.0
    mock_fetch.return_value = cd
    mock_classify.return_value = None

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        current_price=190.0, user_id=uuid.uuid4(),
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=holding.user_id,
        status="active", why_own_it="Growth play",
        confidence="high", interpretation={
            "watch_hints": [
                {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Revenue must grow"},
            ]
        },
    )

    result = await run_health_check(thesis, holding)

    breached = [w for w in result.watch_hints_status if w.breached]
    assert len(breached) == 1
    assert breached[0].metric == "revenue_growth_yoy"


@pytest.mark.asyncio
@patch("app.services.health_check.fetch_company_data")
@patch("app.services.health_check.classify_event")
async def test_health_check_accepts_decimal_holding_price(mock_classify, mock_fetch):
    mock_fetch.return_value = _make_company_data(price=120.0)
    mock_classify.return_value = SimpleNamespace(severity="warning", analysis="Price move matters.")

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        current_price=Decimal("100.0"), user_id=uuid.uuid4(),
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=holding.user_id,
        status="active", why_own_it="AI hardware play",
        confidence="medium",
        interpretation={"watch_hints": [{"kind": "price_move_pct", "threshold": 10.0}]},
    )

    result = await run_health_check(thesis, holding)

    assert result.current_price == 120.0
    assert any(candidate.event_type == "price_move" for candidate in result.candidates)


@pytest.mark.asyncio
@patch("app.services.health_check.generate_monitoring_candidates")
@patch("app.services.health_check.fetch_company_data")
@patch("app.services.health_check.classify_event")
async def test_health_check_graceful_on_classification_failure(mock_classify, mock_fetch, mock_candidates):
    mock_fetch.return_value = _make_company_data()
    mock_candidates.return_value = [
        {"event_type": "price_move", "description": "Price moved 8% since the last check."}
    ]
    mock_classify.side_effect = RuntimeError("LLM timeout")

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        current_price=190.0, user_id=uuid.uuid4(),
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=holding.user_id,
        status="active", why_own_it="AI hardware play",
        confidence="medium",
    )

    result = await run_health_check(thesis, holding)

    assert len(result.candidates) == 1
    assert result.candidates[0].event_type == "price_move"
    assert result.candidates[0].severity is None
    assert result.candidates[0].ai_analysis is None
    assert result.thesis_assessment == "watch"


@pytest.mark.asyncio
async def test_health_check_endpoint_404(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/theses/{fake_id}/health-check", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("app.services.health_check.fetch_company_data")
@patch("app.services.health_check.classify_event")
async def test_health_check_endpoint_success(mock_classify, mock_fetch, client, auth_headers, test_user, db):
    mock_fetch.return_value = _make_company_data()
    mock_classify.return_value = None

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI hardware play",
        confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.post(f"/api/theses/{thesis.id}/health-check", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "AAPL"
    assert data["thesis_id"] == str(thesis.id)
    assert data["thesis_assessment"] in ("all_clear", "watch", "review_needed")
    assert "candidates" in data
    assert "watch_hints_status" in data
