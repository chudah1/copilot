import pytest


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
