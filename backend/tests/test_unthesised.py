import pytest


@pytest.mark.asyncio
async def test_unthesised_returns_holdings_without_active_thesis(client, auth_headers, db, test_user):
    # Create two holdings
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)
    h2 = await client.post("/api/portfolio/holdings", json={
        "ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300,
    }, headers=auth_headers)

    # Create thesis only for AAPL
    await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Ecosystem and margins.",
        "what_would_change_my_mind": "Revenue decline or margin compression.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    tickers = [h["ticker"] for h in response.json()]
    assert tickers == ["MSFT"]


@pytest.mark.asyncio
async def test_unthesised_returns_empty_when_all_have_theses(client, auth_headers, db, test_user):
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder.",
        "what_would_change_my_mind": "Revenue decline or margin compression.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_unthesised_excludes_invalidated_theses(client, auth_headers, db, test_user):
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    create_resp = await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Old thesis.",
        "what_would_change_my_mind": "Revenue decline or margin compression.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    # Invalidate it
    await client.post(
        f"/api/theses/{create_resp.json()['id']}/invalidate",
        json={"reason": "No longer valid"},
        headers=auth_headers,
    )

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["ticker"] == "AAPL"


@pytest.mark.asyncio
async def test_unthesised_requires_auth(client):
    response = await client.get("/api/portfolio/holdings/unthesised")
    assert response.status_code == 403
