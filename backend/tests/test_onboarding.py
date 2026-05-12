async def test_onboarding_status_new_user(client, auth_headers, test_user):
    response = await client.get("/api/onboarding/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["completed"] is False
    assert data["current_step"] == "import_holdings"
    assert data["steps"]["import_holdings"]["done"] is False
    assert data["steps"]["import_holdings"]["count"] == 0
    assert data["steps"]["write_first_thesis"]["done"] is False
    assert data["steps"]["write_first_thesis"]["count"] == 0


async def test_onboarding_after_adding_holdings(client, auth_headers, test_user):
    await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is False
    assert data["current_step"] == "write_first_thesis"
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["import_holdings"]["count"] == 1
    assert data["steps"]["write_first_thesis"]["done"] is False


async def test_onboarding_completes_after_first_thesis(client, auth_headers, test_user, db):
    h = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder with durable ecosystem.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is True
    assert data["current_step"] is None
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["write_first_thesis"]["done"] is True
    assert data["steps"]["write_first_thesis"]["count"] == 1
    assert data["steps"]["review_portfolio_health"]["done"] is True


async def test_onboarding_already_completed_user_stays_completed(client, auth_headers, test_user, db):
    h = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    # First call completes onboarding
    await client.get("/api/onboarding/status", headers=auth_headers)

    # Second call should still be completed
    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is True


async def test_onboarding_requires_auth(client):
    response = await client.get("/api/onboarding/status")
    assert response.status_code == 403
