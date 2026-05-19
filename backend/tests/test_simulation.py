import uuid
from dataclasses import field
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.market_data import CompanyData
from app.services.simulation import simulate_trade


def _make_company_data(ticker: str = "NVDA", name: str = "NVIDIA Corp", sector: str = "Technology") -> CompanyData:
    return CompanyData(
        ticker=ticker, name=name, sector=sector, industry="Semiconductors",
        current_price=100.0, market_cap=2_000_000_000_000, pe_ratio=60.0,
        revenue_growth_yoy=0.12, earnings_growth_yoy=0.15, dividend_yield=0.01,
        description="", recent_news=[], upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None, news_items=[],
    )


@pytest.mark.asyncio
async def test_simulate_new_ticker(db: AsyncSession, test_user):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_price=160, current_value=1600,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    with patch("app.services.simulation.fetch_company_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _make_company_data()
        result = await simulate_trade(test_user.id, "NVDA", 5, 100.0, db)

    assert result.ticker == "NVDA"
    assert result.name == "NVIDIA Corp"
    assert result.simulated_value == 500.0
    assert result.before.holdings_count == 1
    assert result.after.holdings_count == 2
    assert result.after.total_value == 1600 + 500


@pytest.mark.asyncio
async def test_simulate_existing_ticker(db: AsyncSession, test_user):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_price=160, current_value=1600,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    result = await simulate_trade(test_user.id, "AAPL", 5, 160.0, db)

    assert result.ticker == "AAPL"
    assert result.after.holdings_count == 1  # merged, not added
    assert result.after.total_value == 1600 + 800  # existing + simulated


@pytest.mark.asyncio
async def test_simulate_concentration_warning(db: AsyncSession, test_user):
    # One small holding, simulate a huge purchase
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=1, average_cost_basis=10, currency="GBP",
        current_price=10, current_value=10,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    with patch("app.services.simulation.fetch_company_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _make_company_data()
        result = await simulate_trade(test_user.id, "NVDA", 100, 100.0, db)

    warning_types = [w.warning_type for w in result.warnings]
    assert "concentration" in warning_types


@pytest.mark.asyncio
async def test_simulate_missing_thesis_warning(db: AsyncSession, test_user):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1500,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    with patch("app.services.simulation.fetch_company_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _make_company_data(name="NVIDIA", sector="Technology")
        result = await simulate_trade(test_user.id, "NVDA", 5, 100.0, db)

    warning_types = [w.warning_type for w in result.warnings]
    assert "missing_thesis" in warning_types


@pytest.mark.asyncio
async def test_simulate_endpoint(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1500,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    with patch("app.services.simulation.fetch_company_data", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = _make_company_data(name="NVIDIA", sector="Tech")
        resp = await client.post(
            "/api/portfolio/simulate",
            json={"ticker": "NVDA", "quantity": 5, "price_per_share": 100.0},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "NVDA"
    assert data["before"]["holdings_count"] == 1
    assert data["after"]["holdings_count"] == 2
    assert len(data["warnings"]) >= 0


@pytest.mark.asyncio
async def test_simulate_existing_ticker_respects_zero_current_value(db: AsyncSession, test_user):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_price=0, current_value=0,
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    result = await simulate_trade(test_user.id, "AAPL", 5, 20.0, db)

    assert result.before.total_value == 0
    assert result.after.total_value == 100.0
