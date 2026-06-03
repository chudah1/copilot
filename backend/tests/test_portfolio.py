import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.thesis import Thesis
from app.services.market_data import CompanyData


@pytest.fixture(autouse=True)
def _stub_market_calls():
    """Keep holding-creation deterministic and off the network. Empty provider
    currency falls back to the request's currency (preserving prior behaviour) and
    FX=1.0 keeps cost figures identity, so value/cost assertions are unaffected; the
    new provider-currency + native-avg-cost code paths still execute."""
    with patch("app.routes.portfolio.fetch_company_overview", new_callable=AsyncMock,
               return_value={"name": "", "sector": "Unknown", "country": "Unknown", "currency": ""}), \
         patch("app.routes.portfolio.refresh_holding_price", new_callable=AsyncMock, return_value=False), \
         patch("app.services.valuation.get_fx_rate", new_callable=AsyncMock, return_value=1.0):
        yield


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
    # Pin prices off so value-weighted coverage is deterministic (manual add now
    # fetches a live price; without this the weighting would track the live market).
    with patch("app.routes.portfolio.refresh_holding_price", new_callable=AsyncMock, return_value=False):
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
async def test_portfolio_summary_monitoring_ready_for_yfinance_without_alpha_vantage_key(client, auth_headers):
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )

    with patch("app.routes.portfolio.settings") as mock_settings:
        mock_settings.enable_scheduler = True
        mock_settings.market_data_provider = "yfinance"
        mock_settings.alpha_vantage_api_key = ""

        response = await client.get("/api/portfolio/summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["monitoring_ready"] is True
    # yfinance needs no API key, so monitoring is ready. No thesis exists yet,
    # so the message prompts for one rather than describing the live cadence.
    assert data["monitoring_message"].startswith("Monitoring is on")


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


@pytest.mark.asyncio
@patch("app.services.earnings_service._fetch_earnings_date")
async def test_upcoming_earnings_excludes_past_dates(mock_fetch_earnings_date, client, auth_headers):
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
        if ticker == "AAPL":
            return datetime.now(timezone.utc) - timedelta(days=2)
        return datetime.now(timezone.utc) + timedelta(days=3)

    mock_fetch_earnings_date.side_effect = _mock_earnings

    response = await client.get("/api/portfolio/upcoming-earnings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "MSFT"
    assert data[0]["days_until"] >= 0


@pytest.mark.asyncio
async def test_add_manual_note_to_conviction_log(client, auth_headers, db, test_user):
    holding_response = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    holding_id = holding_response.json()["id"]

    thesis_response = await client.post(
        "/api/theses",
        json={
            "holding_id": holding_id,
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Ecosystem strength.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    assert thesis_response.status_code == 201
    thesis_id = thesis_response.json()["id"]

    response = await client.post(
        f"/api/portfolio/holdings/{holding_id}/conviction-log",
        json={"content": "Need to revisit this after earnings."},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entry_type"] == "manual_note"
    assert data["content"] == "Need to revisit this after earnings."
    assert data["thesis_id"] == thesis_id

    log_entries = (await db.execute(select(ConvictionLogEntry).where(ConvictionLogEntry.holding_id == holding_id))).scalars().all()
    assert len(log_entries) == 2  # reason_created + manual_note
