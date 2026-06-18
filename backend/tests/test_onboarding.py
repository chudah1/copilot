from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.services.ai_thesis import SynthesisOutput
from app.models.earnings_calendar import EarningsCalendar
from app.services.onboarding import get_or_create_state
from app.services.trading212 import Trading212Position


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
        "what_would_change_my_mind": "Revenue decline or margin compression.",
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
        "what_would_change_my_mind": "Revenue decline or margin compression.",
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


async def test_onboarding_profile_can_be_saved_and_loaded(client, auth_headers):
    response = await client.post(
        "/api/onboarding/profile",
        json={"investor_profile": "hearsay_driven"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["investor_profile"] == "hearsay_driven"

    state_response = await client.get("/api/onboarding/state", headers=auth_headers)
    assert state_response.status_code == 200
    assert state_response.json()["investor_profile"] == "hearsay_driven"


async def test_onboarding_synthesize_creates_active_wizard_thesis(client, auth_headers):
    holding = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)
    assert holding.status_code == 201

    create = await client.post(
        "/api/onboarding/synthesize",
        json={
            "holding_id": holding.json()["id"],
            "investor_profile": "thesis_driven",
            "question1": "What is the core thesis behind owning this position?",
            "answer1": "Services keeps compounding.",
            "question2": "What would break the thesis?",
            "answer2": "If Services growth breaks and regulation changes the economics.",
        },
        headers=auth_headers,
    )
    assert create.status_code == 201
    thesis_id = create.json()["thesis_id"]

    before = await client.get("/api/theses/current", headers=auth_headers)
    assert before.status_code == 200
    assert before.json()[0]["id"] == thesis_id
    assert before.json()[0]["status"] == "active"

    complete = await client.post("/api/onboarding/complete", headers=auth_headers)
    assert complete.status_code == 204

    after = await client.get("/api/theses/current", headers=auth_headers)
    assert after.status_code == 200
    assert after.json()[0]["id"] == thesis_id
    assert after.json()[0]["status"] == "active"


async def test_synthesize_uses_investor_profile_from_request(client, auth_headers):
    holding = await client.post("/api/portfolio/holdings", json={
        "ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900,
    }, headers=auth_headers)
    assert holding.status_code == 201

    mock_output = SynthesisOutput(
        why_own_it="This started from AI excitement, but the real reason to own it is durable demand for accelerated compute.",
        must_remain_true="AI infrastructure demand and pricing power remain intact.",
        what_would_change_my_mind="If the growth story stops showing up in actual results.",
        ai_summary="A rough AI idea has been turned into a demand-driven thesis.",
        interpretation={"labels": ["growth"], "monitorability": "medium", "watch_hints": [], "proxy_signals": [], "ambiguity_note": ""},
    )
    with patch("app.routes.onboarding.synthesize_thesis_from_qa", new_callable=AsyncMock, return_value=mock_output) as mock_synthesize:
        response = await client.post(
            "/api/onboarding/synthesize",
            json={
                "holding_id": holding.json()["id"],
                "investor_profile": "hearsay_driven",
                "question1": "What made this stock interesting enough to buy in the first place?",
                "answer1": "Everyone was talking about AI leaders.",
                "question2": "What would make you admit the original idea is no longer working?",
                "answer2": "If growth no longer shows up in the numbers.",
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert mock_synthesize.await_args.kwargs["investor_profile"] == "hearsay_driven"


async def test_onboarding_after_broker_sync(client, auth_headers):
    _live_url = "https://live.trading212.com/api/v0"
    with patch("app.routes.portfolio.detect_trading212_base_url", new_callable=AsyncMock, return_value=_live_url):
        connect_response = await client.post(
            "/api/portfolio/connect",
            json={"broker_type": "trading212", "api_key": "test-key"},
            headers=auth_headers,
        )
    assert connect_response.status_code == 201
    connection_id = connect_response.json()["id"]

    fake_position = Trading212Position(
        ticker="AAPL",
        quantity=10.0,
        average_price=150.0,
        current_price=175.0,
        ppl=250.0,
        fx_ppl=200.0,
    )
    with patch("app.routes.portfolio.detect_trading212_base_url", new_callable=AsyncMock, return_value=_live_url):
        with patch("app.routes.portfolio.Trading212Client.fetch_positions", new_callable=AsyncMock, return_value=[fake_position]):
            with patch("app.routes.portfolio.fetch_company_overview", new_callable=AsyncMock, return_value=None):
                sync_response = await client.post(f"/api/portfolio/sync/{connection_id}", headers=auth_headers)

    assert sync_response.status_code == 200

    status_response = await client.get("/api/onboarding/status", headers=auth_headers)
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["import_holdings"]["count"] == 1
    assert data["current_step"] == "write_first_thesis"


async def test_onboarding_banner_prefers_soonest_earnings_when_multiple_uncovered(client, auth_headers, db, test_user):
    hold1 = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    hold2 = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300},
        headers=auth_headers,
    )
    hold3 = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 3, "average_cost_basis": 500},
        headers=auth_headers,
    )

    await client.post(
        "/api/theses",
        json={
            "holding_id": hold1.json()["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple ecosystem.",
            "what_would_change_my_mind": "Revenue decline or margin compression.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )

    state = await get_or_create_state(db, test_user.id)
    state.first_reason_written_at = datetime.now(timezone.utc) - timedelta(hours=25)

    db.add(EarningsCalendar(
        ticker="MSFT",
        report_date=datetime.now(timezone.utc) + timedelta(days=10),
        source="test",
    ))
    db.add(EarningsCalendar(
        ticker="NVDA",
        report_date=datetime.now(timezone.utc) + timedelta(days=3),
        source="test",
    ))
    await db.commit()

    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["show"] is True
    assert data["banner_type"] == "add_more_reasons"
    assert data["suggested_holding"]["ticker"] == "NVDA"
