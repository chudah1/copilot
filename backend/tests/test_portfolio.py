import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.thesis import Thesis
from app.services.market_data import CompanyData


@pytest.mark.asyncio
async def test_add_manual_holding(client, auth_headers):
    response = await client.post(
        "/api/portfolio/holdings",
        json={
            "ticker": "AAPL",
            "name": "Apple Inc",
            "quantity": 10,
            "average_cost_basis": 150.50,
            "currency": "USD",
            "sector": "Technology",
            "geography": "US",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert data["quantity"] == 10.0


@pytest.mark.asyncio
async def test_list_holdings(client, auth_headers):
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300},
        headers=auth_headers,
    )
    response = await client.get("/api/portfolio/holdings", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_list_holdings_requires_auth(client):
    response = await client.get("/api/portfolio/holdings")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_portfolio_summary(client, auth_headers):
    await client.post(
        "/api/portfolio/holdings",
        json={
            "ticker": "AAPL",
            "name": "Apple",
            "quantity": 10,
            "average_cost_basis": 150,
            "sector": "Technology",
            "geography": "US",
        },
        headers=auth_headers,
    )
    response = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["holdings_count"] == 1
    assert data["theses_missing"] == 1
    assert data["top_3_concentration_pct"] == 100.0
    assert data["thesis_coverage_pct"] == 0.0
    assert data["unmonitored_holdings_count"] == 1
    assert len(data["attention_queue"]) == 1
    assert data["attention_queue"][0]["ticker"] == "AAPL"
    assert "Monitoring is" in data["monitoring_message"]


@pytest.mark.asyncio
async def test_portfolio_summary_counts_active_and_stale_theses(client, auth_headers, db, test_user):
    holding_response = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    holding_id = holding_response.json()["id"]

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding_id,
        status="active",
        thesis_kind="company",
        why_own_it="Hold for ecosystem strength.",
        confidence="high",
        review_cadence_days=7,
        source="user",
        updated_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    db.add(thesis)
    await db.commit()

    response = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["theses_active"] == 0
    assert data["theses_need_review"] == 1
    assert data["theses_missing"] == 0
    assert data["stale_theses_count"] == 1
    assert data["thesis_coverage_pct"] == 100.0
    assert data["attention_queue"][0]["reason"].startswith("This thesis is stale")


@pytest.mark.asyncio
async def test_portfolio_summary_tracks_monitorability_and_conviction_mismatch(client, auth_headers, db, test_user):
    first = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 10, "average_cost_basis": 100},
        headers=auth_headers,
    )
    second = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "META", "name": "Meta", "quantity": 5, "average_cost_basis": 100},
        headers=auth_headers,
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    db.add(
        Thesis(
            user_id=test_user.id,
            holding_id=first_id,
            status="active",
            thesis_kind="company",
            why_own_it="AI demand and margins stay strong.",
            confidence="high",
            review_cadence_days=7,
            interpretation={
                "monitorability": "high",
                "watch_hints": [{"kind": "price_move_pct", "threshold": 10.0, "rationale": "Review sharp moves."}],
            },
            source="ai_assisted",
        )
    )
    db.add(
        Thesis(
            user_id=test_user.id,
            holding_id=second_id,
            status="active",
            thesis_kind="company",
            why_own_it="My friend recommended it.",
            confidence="low",
            review_cadence_days=7,
            interpretation={"monitorability": "low", "watch_hints": []},
            source="user",
        )
    )
    await db.commit()

    response = await client.get("/api/portfolio/summary", headers=auth_headers)
    data = response.json()
    assert data["thesis_coverage_pct"] == 100.0
    assert data["monitorable_thesis_coverage_pct"] > 60.0
    assert data["unmonitored_holdings_count"] == 1
    assert data["conviction_mismatch_count"] == 1


@pytest.mark.asyncio
@patch("app.services.earnings_service._fetch_earnings_date")
async def test_upcoming_earnings_returns_sorted_items(mock_fetch_earnings_date, client, auth_headers):
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300},
        headers=auth_headers,
    )

    async def _mock_earnings(ticker: str) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=5 if ticker == "AAPL" else 2)

    mock_fetch_earnings_date.side_effect = _mock_earnings

    response = await client.get("/api/portfolio/upcoming-earnings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "MSFT"
    assert data[1]["ticker"] == "AAPL"
    assert data[0]["days_until"] <= data[1]["days_until"]
