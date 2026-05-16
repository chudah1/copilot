from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.jobs.onboarding_drip import run_onboarding_drip
from app.models.holding import Holding
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password
from app.services.onboarding import (
    get_or_create_state,
    mark_portfolio_connected,
    mark_reason_written,
    mark_digest_received,
    is_onboarding_complete,
    coverage_pct,
)


# --- Service unit tests ---


@pytest.mark.asyncio
async def test_get_or_create_state_creates_new(db, test_user):
    state = await get_or_create_state(db, test_user.id)
    await db.commit()
    assert state.user_id == test_user.id
    assert state.portfolio_connected_at is None
    assert state.reasons_written_count == 0


@pytest.mark.asyncio
async def test_get_or_create_state_returns_existing(db, test_user):
    state1 = await get_or_create_state(db, test_user.id)
    await db.commit()
    state2 = await get_or_create_state(db, test_user.id)
    assert state1.id == state2.id


@pytest.mark.asyncio
async def test_mark_portfolio_connected(db, test_user):
    await mark_portfolio_connected(db, test_user.id)
    await db.commit()
    state = await get_or_create_state(db, test_user.id)
    assert state.portfolio_connected_at is not None


@pytest.mark.asyncio
async def test_mark_portfolio_connected_idempotent(db, test_user):
    await mark_portfolio_connected(db, test_user.id)
    await db.commit()
    state = await get_or_create_state(db, test_user.id)
    first_connected = state.portfolio_connected_at

    await mark_portfolio_connected(db, test_user.id)
    await db.commit()
    state = await get_or_create_state(db, test_user.id)
    assert state.portfolio_connected_at == first_connected


@pytest.mark.asyncio
async def test_mark_reason_written_increments_count(db, test_user):
    await mark_reason_written(db, test_user.id)
    await mark_reason_written(db, test_user.id)
    await db.commit()
    state = await get_or_create_state(db, test_user.id)
    assert state.reasons_written_count == 2
    assert state.first_reason_written_at is not None


@pytest.mark.asyncio
async def test_mark_digest_received_sets_completed(db, test_user):
    await mark_digest_received(db, test_user.id)
    await db.commit()
    state = await get_or_create_state(db, test_user.id)
    assert state.first_digest_received_at is not None
    assert state.onboarding_completed_at is not None


@pytest.mark.asyncio
async def test_is_onboarding_complete_false_when_no_reasons(db, test_user):
    state = await get_or_create_state(db, test_user.id)
    assert not is_onboarding_complete(state, holdings_count=3)


@pytest.mark.asyncio
async def test_is_onboarding_complete_true_when_full_coverage(db, test_user):
    state = await get_or_create_state(db, test_user.id)
    state.reasons_written_count = 3
    assert is_onboarding_complete(state, holdings_count=3)


@pytest.mark.asyncio
async def test_coverage_pct(db, test_user):
    state = await get_or_create_state(db, test_user.id)
    state.reasons_written_count = 2
    assert coverage_pct(state, holdings_count=4) == 50.0


# --- Banner endpoint tests ---


@pytest.mark.asyncio
async def test_banner_no_holdings(client, auth_headers):
    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["show"] is False


@pytest.mark.asyncio
async def test_banner_has_holdings_no_reasons(client, auth_headers):
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["show"] is True
    assert data["banner_type"] == "start_first_reason"
    assert "AAPL" in data["message"] or "1 holding" in data["message"]


@pytest.mark.asyncio
async def test_banner_first_reason_monitoring(client, auth_headers):
    hold = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    await client.post(
        "/api/theses",
        json={
            "holding_id": hold.json()["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple ecosystem lock-in.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["show"] is True
    assert data["banner_type"] == "first_reason_monitoring"


@pytest.mark.asyncio
async def test_banner_add_more_reasons(client, auth_headers, db, test_user):
    hold1 = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300},
        headers=auth_headers,
    )

    await client.post(
        "/api/theses",
        json={
            "holding_id": hold1.json()["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple ecosystem.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )

    # Push first_reason_written_at back 25h to skip monitoring confirmation
    state = await get_or_create_state(db, test_user.id)
    state.first_reason_written_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await db.commit()

    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["show"] is True
    assert data["banner_type"] == "add_more_reasons"
    assert data["suggested_holding"] is not None
    assert data["suggested_holding"]["ticker"] == "MSFT"


@pytest.mark.asyncio
async def test_banner_hidden_above_50pct(client, auth_headers, db, test_user):
    for ticker, name in [("AAPL", "Apple"), ("MSFT", "Microsoft")]:
        hold = await client.post(
            "/api/portfolio/holdings",
            json={"ticker": ticker, "name": name, "quantity": 5, "average_cost_basis": 100},
            headers=auth_headers,
        )
        await client.post(
            "/api/theses",
            json={
                "holding_id": hold.json()["id"],
                "status": "active",
                "thesis_kind": "company",
                "why_own_it": f"Holding {ticker} for growth.",
                "confidence": "high",
                "review_cadence_days": 7,
                "source": "user",
            },
            headers=auth_headers,
        )
    # Push first_reason_written_at back to bypass monitoring confirmation window
    state = await get_or_create_state(db, test_user.id)
    state.first_reason_written_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await db.commit()

    # 2 holdings, 2 reasons = 100% coverage > 50%
    response = await client.get("/api/onboarding/banner", headers=auth_headers)
    data = response.json()
    assert data["show"] is False


# --- Drip job tests ---


@pytest.mark.asyncio
async def test_drip_skips_completed_users(db, job_session_factory):
    user = User(email="drip_complete@example.com", password_hash=hash_password("pass"))
    db.add(user)
    await db.flush()
    state = OnboardingState(
        user_id=user.id,
        portfolio_connected_at=datetime.now(timezone.utc) - timedelta(days=3),
        onboarding_completed_at=datetime.now(timezone.utc),
    )
    db.add(state)
    await db.commit()

    with patch("app.jobs.onboarding_drip.async_session", job_session_factory):
        with patch("app.jobs.onboarding_drip.send_onboarding_email", new_callable=AsyncMock) as mock_send:
            await run_onboarding_drip()
    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_drip_sends_day1_email_after_first_reason(db, job_session_factory):
    user = User(email="drip_day1@example.com", password_hash=hash_password("pass"))
    db.add(user)
    await db.flush()

    holding = Holding(user_id=user.id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100)
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Apple ecosystem.",
        confidence="high",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    state = OnboardingState(
        user_id=user.id,
        portfolio_connected_at=datetime.now(timezone.utc) - timedelta(days=2),
        first_reason_written_at=datetime.now(timezone.utc) - timedelta(hours=26),
        reasons_written_count=1,
    )
    db.add(state)
    await db.commit()

    with patch("app.jobs.onboarding_drip.async_session", job_session_factory):
        with patch("app.jobs.onboarding_drip.send_onboarding_email", new_callable=AsyncMock, return_value=True) as mock_send:
            await run_onboarding_drip()

    mock_send.assert_awaited_once()
    call_kwargs = mock_send.await_args
    assert "Apple" in call_kwargs[0][0] or "Apple" in call_kwargs[0][1]

    state_after = (await db.execute(select(OnboardingState).where(OnboardingState.user_id == user.id))).scalar_one()
    assert state_after.day1_email_sent_at is not None
    assert state_after.last_email_sent_at is not None


@pytest.mark.asyncio
async def test_drip_respects_1_email_per_day(db, job_session_factory):
    user = User(email="drip_ratelimit@example.com", password_hash=hash_password("pass"))
    db.add(user)
    await db.flush()

    holding = Holding(user_id=user.id, ticker="TSLA", name="Tesla", quantity=5, average_cost_basis=200)
    db.add(holding)
    await db.flush()

    state = OnboardingState(
        user_id=user.id,
        portfolio_connected_at=datetime.now(timezone.utc) - timedelta(days=6),
        first_reason_written_at=datetime.now(timezone.utc) - timedelta(days=5),
        reasons_written_count=0,
        last_email_sent_at=datetime.now(timezone.utc) - timedelta(hours=2),  # too recent
    )
    db.add(state)
    await db.commit()

    with patch("app.jobs.onboarding_drip.async_session", job_session_factory):
        with patch("app.jobs.onboarding_drip.send_onboarding_email", new_callable=AsyncMock, return_value=True) as mock_send:
            await run_onboarding_drip()

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_drip_sends_day5_email_when_low_coverage(db, job_session_factory):
    user = User(email="drip_day5@example.com", password_hash=hash_password("pass"))
    db.add(user)
    await db.flush()

    for ticker, name in [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("TSLA", "Tesla")]:
        db.add(Holding(user_id=user.id, ticker=ticker, name=name, quantity=5, average_cost_basis=100))
    await db.flush()

    state = OnboardingState(
        user_id=user.id,
        portfolio_connected_at=datetime.now(timezone.utc) - timedelta(days=6),
        first_reason_written_at=datetime.now(timezone.utc) - timedelta(days=5),
        reasons_written_count=0,
        day1_email_sent_at=datetime.now(timezone.utc) - timedelta(days=4),
        last_email_sent_at=datetime.now(timezone.utc) - timedelta(days=1, hours=1),
    )
    db.add(state)
    await db.commit()

    with patch("app.jobs.onboarding_drip.async_session", job_session_factory):
        with patch("app.jobs.onboarding_drip.send_onboarding_email", new_callable=AsyncMock, return_value=True) as mock_send:
            await run_onboarding_drip()

    mock_send.assert_awaited_once()
    subject = mock_send.await_args[0][1]
    assert "no reason" in subject

    state_after = (await db.execute(select(OnboardingState).where(OnboardingState.user_id == user.id))).scalar_one()
    assert state_after.day5_email_sent_at is not None


# --- Hook integration tests ---


@pytest.mark.asyncio
async def test_add_holding_triggers_portfolio_connected(client, auth_headers, db, test_user):
    await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    state = (await db.execute(select(OnboardingState).where(OnboardingState.user_id == test_user.id))).scalar_one_or_none()
    assert state is not None
    assert state.portfolio_connected_at is not None


@pytest.mark.asyncio
async def test_create_thesis_triggers_reason_written(client, auth_headers, db, test_user):
    hold = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    await client.post(
        "/api/theses",
        json={
            "holding_id": hold.json()["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple is a quality compounder.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    state = (await db.execute(select(OnboardingState).where(OnboardingState.user_id == test_user.id))).scalar_one()
    assert state.first_reason_written_at is not None
    assert state.reasons_written_count == 1
