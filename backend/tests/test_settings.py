"""Tests for Phase 8: notification preferences."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.digest import Digest
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.routes.settings import UserPreferences, get_user_prefs
from app.services.auth import hash_password


# --- Existing tests (kept unchanged) ---


async def test_get_settings_normalizes_unsupported_digest_frequency(client, auth_headers, db, test_user):
    test_user.preferences = {
        "digest_frequency": "daily",
        "notification_sensitivity": "all",
    }
    await db.commit()

    response = await client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["digest_frequency"] == "weekly"


async def test_update_settings_persists_supported_values_only(client, auth_headers, db, test_user):
    response = await client.put(
        "/api/settings",
        json={
            "digest_frequency": "weekly",
            "notification_sensitivity": "thesis_breaking_only",
            "email_enabled": True,
            "earnings_alerts": True,
            "quarterly_review_reminders": True,
            "digest_day": "sunday",
            "digest_time": "17:00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["digest_frequency"] == "weekly"
    assert response.json()["notification_sensitivity"] == "thesis_breaking_only"

    await db.refresh(test_user)
    assert test_user.preferences["digest_frequency"] == "weekly"
    assert test_user.preferences["notification_sensitivity"] == "thesis_breaking_only"


# --- New Phase 8 tests ---


async def test_display_name_round_trip_and_partial_update(client, auth_headers, db, test_user):
    # Partial body: only display_name — other preferences must survive the merge.
    test_user.preferences = {"digest_frequency": "monthly"}
    await db.commit()

    response = await client.put(
        "/api/settings",
        json={"display_name": "  Kwasi  "},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Kwasi"  # stripped
    assert body["digest_frequency"] == "monthly"  # preserved

    fetched = await client.get("/api/settings", headers=auth_headers)
    assert fetched.json()["display_name"] == "Kwasi"


async def test_display_name_defaults_empty_and_ignores_non_string(client, auth_headers, db, test_user):
    test_user.preferences = {"display_name": 42}
    await db.commit()

    response = await client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["display_name"] == ""


def test_display_name_capped_at_40_chars():
    prefs = UserPreferences(display_name="x" * 60)
    assert len(prefs.display_name) == 40


def test_invalid_frequency_defaults_to_weekly():
    prefs = UserPreferences(digest_frequency="hourly")
    assert prefs.digest_frequency == "weekly"


def test_valid_frequencies_accepted():
    for freq in ("weekly", "fortnightly", "monthly", "none"):
        assert UserPreferences(digest_frequency=freq).digest_frequency == freq


def test_invalid_day_defaults_to_sunday():
    prefs = UserPreferences(digest_day="funday")
    assert prefs.digest_day == "sunday"


def test_invalid_time_defaults_to_1700():
    prefs = UserPreferences(digest_time="25:99")
    assert prefs.digest_time == "17:00"


def test_valid_time_normalised():
    prefs = UserPreferences(digest_time="9:05")
    assert prefs.digest_time == "09:05"


def test_portfolio_currency_is_normalized_and_invalid_values_fall_back():
    assert UserPreferences(portfolio_currency="usd").portfolio_currency == "USD"
    assert UserPreferences(portfolio_currency="not-a-currency").portfolio_currency == "GBP"


def test_get_user_prefs_applies_defaults():
    class FakeUser:
        preferences = {}
    prefs = get_user_prefs(FakeUser())
    assert prefs.email_enabled is True
    assert prefs.earnings_alerts is True
    assert prefs.quarterly_review_reminders is True
    assert prefs.portfolio_currency == "GBP"


def test_get_user_prefs_reads_stored_values():
    class FakeUser:
        preferences = {
            "email_enabled": False,
            "earnings_alerts": False,
            "digest_frequency": "monthly",
            "digest_day": "friday",
            "digest_time": "08:00",
        }
    prefs = get_user_prefs(FakeUser())
    assert prefs.email_enabled is False
    assert prefs.earnings_alerts is False
    assert prefs.digest_frequency == "monthly"
    assert prefs.digest_day == "friday"
    assert prefs.digest_time == "08:00"


def test_get_user_prefs_normalizes_string_bools():
    class FakeUser:
        preferences = {
            "email_enabled": "false",
            "earnings_alerts": "0",
            "quarterly_review_reminders": "yes",
        }

    prefs = get_user_prefs(FakeUser())
    assert prefs.email_enabled is False
    assert prefs.earnings_alerts is False
    assert prefs.quarterly_review_reminders is True


@pytest.mark.asyncio
async def test_put_settings_saves_all_fields(client, auth_headers):
    response = await client.put(
        "/api/settings",
        json={
            "digest_frequency": "fortnightly",
            "digest_day": "friday",
            "digest_time": "08:00",
            "earnings_alerts": False,
            "quarterly_review_reminders": False,
            "email_enabled": False,
            "notification_sensitivity": "thesis_breaking_only",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["digest_frequency"] == "fortnightly"
    assert data["digest_day"] == "friday"
    assert data["digest_time"] == "08:00"
    assert data["earnings_alerts"] is False
    assert data["quarterly_review_reminders"] is False
    assert data["email_enabled"] is False

    get = await client.get("/api/settings", headers=auth_headers)
    assert get.json()["email_enabled"] is False


@pytest.mark.asyncio
async def test_put_settings_preserves_unrelated_keys(client, auth_headers, db, test_user):
    test_user.preferences = {"consecutive_quiet_weeks": 3}
    await db.commit()

    await client.put(
        "/api/settings",
        json={
            "digest_frequency": "monthly",
            "email_enabled": True,
            "earnings_alerts": True,
            "quarterly_review_reminders": True,
            "digest_day": "sunday",
            "digest_time": "17:00",
            "notification_sensitivity": "all",
        },
        headers=auth_headers,
    )
    await db.refresh(test_user)
    assert test_user.preferences.get("consecutive_quiet_weeks") == 3


@pytest.mark.asyncio
async def test_digest_skips_user_with_email_disabled(db, job_session_factory):
    user = User(
        email="noemail@example.com",
        password_hash=hash_password("pass"),
        preferences={"email_enabled": False},
    )
    db.add(user)
    await db.flush()
    holding = Holding(
        user_id=user.id, ticker="AAPL", name="Apple",
        quantity=10, average_cost_basis=100, current_value=1000,
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="AI demand.", confidence="high",
        review_cadence_days=7, source="user",
    ))
    await db.commit()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock) as mock_send:
            from app.jobs.digest_builder import run_digest_builder
            await run_digest_builder()

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_digest_skips_fortnightly_user_if_sent_recently(db, job_session_factory):
    user = User(
        email="fort@example.com",
        password_hash=hash_password("pass"),
        preferences={"email_enabled": True, "digest_frequency": "fortnightly"},
    )
    db.add(user)
    await db.flush()
    holding = Holding(
        user_id=user.id, ticker="MSFT", name="Microsoft",
        quantity=5, average_cost_basis=200, current_value=1000,
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="Cloud growth.", confidence="high",
        review_cadence_days=14, source="user",
    ))
    recent_period = datetime.now(timezone.utc) - timedelta(days=5)
    db.add(Digest(
        user_id=user.id,
        period_start=recent_period - timedelta(days=7),
        period_end=recent_period,
        content={"html": "<p>test</p>", "digest_mode": "quiet_week"},
        status="sent",
        sent_at=recent_period,
    ))
    await db.commit()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock) as mock_send:
            from app.jobs.digest_builder import run_digest_builder
            await run_digest_builder()

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_digest_sends_fortnightly_user_after_threshold(db, job_session_factory):
    user = User(
        email="fort2@example.com",
        password_hash=hash_password("pass"),
        preferences={"email_enabled": True, "digest_frequency": "fortnightly"},
    )
    db.add(user)
    await db.flush()
    holding = Holding(
        user_id=user.id, ticker="TSLA", name="Tesla",
        quantity=3, average_cost_basis=150, current_value=500,
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="EV market leader.", confidence="medium",
        review_cadence_days=14, source="user",
    ))
    old_period = datetime.now(timezone.utc) - timedelta(days=14)
    db.add(Digest(
        user_id=user.id,
        period_start=old_period - timedelta(days=7),
        period_end=old_period,
        content={"html": "<p>test</p>", "digest_mode": "quiet_week"},
        status="sent",
        sent_at=old_period,
    ))
    await db.commit()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock, return_value=True) as mock_send:
            from app.jobs.digest_builder import run_digest_builder
            await run_digest_builder()

    mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_quarterly_review_nudge_sent_on_new_review(db, test_user, job_session_factory):
    holding = Holding(
        user_id=test_user.id, ticker="ASML", name="ASML",
        quantity=5, average_cost_basis=600, current_value=3000, currency="EUR",
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=test_user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="EUV monopoly.", confidence="high",
        review_cadence_days=30, source="user",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    ))
    test_user.preferences = {"email_enabled": True, "quarterly_review_reminders": True}
    await db.commit()

    with patch("app.jobs.quarterly_review_prep.async_session", job_session_factory):
        with patch("app.jobs.quarterly_review_prep.send_onboarding_email", new_callable=AsyncMock, return_value=True) as mock_send:
            from app.jobs.quarterly_review_prep import run_quarterly_review_prep
            await run_quarterly_review_prep(
                now=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
                session_factory=job_session_factory,
            )

    mock_send.assert_awaited_once()
    subject = mock_send.await_args[0][1]
    assert "Quarterly" in subject
    assert "Q2" in subject


@pytest.mark.asyncio
async def test_quarterly_review_nudge_skipped_when_reminders_off(db, test_user, job_session_factory):
    holding = Holding(
        user_id=test_user.id, ticker="NVDA", name="NVIDIA",
        quantity=5, average_cost_basis=500, current_value=4000, currency="USD",
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=test_user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="AI chips.", confidence="high",
        review_cadence_days=30, source="user",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    ))
    test_user.preferences = {"email_enabled": True, "quarterly_review_reminders": False}
    await db.commit()

    with patch("app.jobs.quarterly_review_prep.async_session", job_session_factory):
        with patch("app.jobs.quarterly_review_prep.send_onboarding_email", new_callable=AsyncMock) as mock_send:
            from app.jobs.quarterly_review_prep import run_quarterly_review_prep
            await run_quarterly_review_prep(
                now=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
                session_factory=job_session_factory,
            )

    mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_quarterly_review_nudge_not_sent_twice(db, test_user, job_session_factory):
    holding = Holding(
        user_id=test_user.id, ticker="SHOP", name="Shopify",
        quantity=10, average_cost_basis=70, current_value=900, currency="USD",
    )
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=test_user.id, holding_id=holding.id, status="active",
        thesis_kind="company", why_own_it="E-commerce platform.", confidence="medium",
        review_cadence_days=30, source="user",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    ))
    test_user.preferences = {"email_enabled": True, "quarterly_review_reminders": True}
    await db.commit()

    run_kwargs = dict(
        now=datetime(2026, 4, 6, 9, 0, tzinfo=timezone.utc),
        session_factory=job_session_factory,
    )

    with patch("app.jobs.quarterly_review_prep.async_session", job_session_factory):
        with patch("app.jobs.quarterly_review_prep.send_onboarding_email", new_callable=AsyncMock, return_value=True) as mock_send:
            from app.jobs.quarterly_review_prep import run_quarterly_review_prep
            await run_quarterly_review_prep(**run_kwargs)
            await run_quarterly_review_prep(**run_kwargs)

    assert mock_send.await_count == 1
