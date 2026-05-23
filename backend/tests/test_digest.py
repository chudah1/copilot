from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.jobs.digest_builder import run_digest_builder
from app.models.digest import Digest
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password


async def test_list_digests_empty(client, auth_headers):
    response = await client.get("/api/digests", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_digests_requires_auth(client):
    response = await client.get("/api/digests")
    assert response.status_code == 403


async def test_digest_builder_records_missing_and_stale_theses(db, job_session_factory):
    user = User(email="digest@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    fresh_holding = Holding(user_id=user.id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100, current_value=1000)
    stale_holding = Holding(user_id=user.id, ticker="MSFT", name="Microsoft", quantity=5, average_cost_basis=200, current_value=1000)
    missing_holding = Holding(user_id=user.id, ticker="TSLA", name="Tesla", quantity=2, average_cost_basis=300, current_value=600)
    db.add_all([fresh_holding, stale_holding, missing_holding])
    await db.flush()

    db.add(
        Thesis(
            user_id=user.id,
            holding_id=fresh_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Apple remains a quality compounder.",
            confidence="high",
            review_cadence_days=7,
            source="user",
        )
    )
    db.add(
        Thesis(
            user_id=user.id,
            holding_id=stale_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Microsoft compounds cloud demand.",
            confidence="high",
            review_cadence_days=7,
            source="user",
            updated_at=datetime.now(timezone.utc) - timedelta(days=100),
        )
    )
    db.add(
        EarningsCalendar(
            ticker="AAPL",
            report_date=datetime.now(timezone.utc) + timedelta(days=9),
            source="test",
        )
    )
    await db.commit()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock, return_value=True) as send_mock:
            await run_digest_builder()

    digest = (await db.execute(select(Digest))).scalar_one()
    html = digest.content["html"]
    assert digest.status == "sent"
    assert "Apple remains a quality compounder." in html
    assert "Your holdings were quiet this week." in html
    assert "Monitoring receipt" in html
    assert "Missing reasons" in html
    assert digest.content["stable_holdings_count"] == 2
    assert digest.content["headline"] == "1 thesis went stale this week."
    assert digest.content["digest_mode"] == "quiet_week"
    assert digest.content["subject_line"] == "2 of your reasons held up this week"
    assert digest.content["missing_theses_count"] == 1
    assert digest.content["stale_theses_count"] == 1
    assert any("Stale theses: MSFT" == point for point in digest.content["summary_points"])
    assert digest.content["next_earnings"]["ticker"] == "AAPL"
    assert "Upcoming:" in html
    assert "We checked 3 holdings with current reasons." in digest.content["monitoring_receipt"]
    send_mock.assert_awaited_once()
    assert send_mock.await_args.kwargs["subject"] == "2 of your reasons held up this week"


async def test_digest_happy_path_after_monitoring_event(client, auth_headers, db, test_user, job_session_factory):
    holding_response = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150},
        headers=auth_headers,
    )
    holding = holding_response.json()

    db_holding = await db.get(Holding, holding["id"])
    db_holding.current_price = 150
    db_holding.current_value = 1500
    await db.commit()

    create_response = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "I own it for resilient ecosystem demand.",
            "must_remain_true": "Customer demand remains strong.",
            "what_would_change_my_mind": "A sustained demand slowdown.",
            "confidence": "high",
            "review_cadence_days": 7,
            "interpretation": {
                "watch_hints": [
                    {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Review sharp moves."}
                ]
            },
            "source": "ai_assisted",
        },
        headers=auth_headers,
    )
    thesis_id = create_response.json()["id"]

    from app.jobs.monitoring_run import run_monitoring

    class StubCompanyData:
        ticker = "AAPL"
        name = "Apple"
        sector = "Technology"
        industry = "Consumer Electronics"
        current_price = 170.0
        market_cap = None
        pe_ratio = None
        revenue_growth_yoy = None
        earnings_growth_yoy = None
        dividend_yield = None
        description = ""
        recent_news = []
        upcoming_earnings_date = None
        recent_earnings_surprise_pct = None
        news_items = []
        provider_payload = {"quote": {"Global Quote": {"05. price": "170.0"}}}

    classification = type("Classification", (), {"severity": "warning", "analysis": "The move should be reviewed against the thesis."})()

    with patch("app.jobs.monitoring_run.settings") as mock_settings:
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_settings.market_data_provider = "alpha_vantage"
        with patch("app.jobs.monitoring_run.async_session", job_session_factory):
            with patch("app.jobs.monitoring_run.fetch_company_data", new_callable=AsyncMock, return_value=StubCompanyData()):
                with patch("app.services.monitoring_pipeline.classify_event", new_callable=AsyncMock, return_value=classification):
                    await run_monitoring()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock, return_value=True) as send_mock:
            await run_digest_builder()

    digest = (await db.execute(select(Digest).where(Digest.user_id == test_user.id))).scalar_one()
    assert digest.status == "sent"
    assert "Your reason:" in digest.content["html"]
    assert "I own it for resilient ecosystem demand." in digest.content["html"]
    assert digest.content["events_count"] == 1
    assert digest.content["stable_holdings_count"] == 0
    assert digest.content["headline"] == "1 of your reasons needs review this week."
    assert digest.content["digest_mode"] == "events"
    assert digest.content["subject_line"] == "1 of your reasons needs review this week"
    assert digest.content["summary_points"][0].startswith("AAPL:")
    assert "Monitoring receipt" in digest.content["html"]
    send_mock.assert_awaited_once()
    assert send_mock.await_args.kwargs["subject"] == "1 of your reasons needs review this week"

    thesis = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    assert thesis.status_code == 200


async def test_digest_builder_rolls_back_failed_user_and_continues(db, job_session_factory):
    first_user = User(email="broken@example.com", password_hash=hash_password("testpass123"))
    second_user = User(email="healthy@example.com", password_hash=hash_password("testpass123"))
    db.add_all([first_user, second_user])
    await db.flush()

    first_holding = Holding(user_id=first_user.id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100, current_value=1000)
    second_holding = Holding(user_id=second_user.id, ticker="MSFT", name="Microsoft", quantity=5, average_cost_basis=200, current_value=1000)
    db.add_all([first_holding, second_holding])
    await db.flush()

    db.add_all([
        Thesis(
            user_id=first_user.id,
            holding_id=first_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Apple remains resilient.",
            confidence="high",
            review_cadence_days=7,
            source="user",
        ),
        Thesis(
            user_id=second_user.id,
            holding_id=second_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Microsoft compounds cloud demand.",
            confidence="high",
            review_cadence_days=7,
            source="user",
        ),
    ])
    await db.commit()

    async def flaky_send(*, to_email: str, subject: str, html_content: str) -> bool:
        if to_email == "broken@example.com":
            raise RuntimeError("SMTP outage")
        return True

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new=flaky_send):
            await run_digest_builder()

    digests = (await db.execute(select(Digest).order_by(Digest.user_id))).scalars().all()
    assert len(digests) == 1
    assert digests[0].user_id == second_user.id
    assert digests[0].status == "sent"


async def test_digest_builder_uses_hearsay_profile_copy(db, job_session_factory):
    user = User(email="story@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    db.add(
        OnboardingState(
            user_id=user.id,
            investor_profile="hearsay_driven",
        )
    )

    holding = Holding(
        user_id=user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=4,
        average_cost_basis=500,
        current_value=2400,
    )
    db.add(holding)
    await db.flush()

    db.add(
        Thesis(
            user_id=user.id,
            holding_id=holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="AI demand should keep driving datacenter GPU growth.",
            confidence="medium",
            review_cadence_days=7,
            source="user",
            updated_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
    )
    await db.commit()

    with patch("app.jobs.digest_builder.async_session", job_session_factory):
        with patch("app.jobs.digest_builder.send_digest_email", new_callable=AsyncMock, return_value=True):
            await run_digest_builder()

    digest = (await db.execute(select(Digest).where(Digest.user_id == user.id))).scalar_one()
    assert digest.content["investor_profile"] == "hearsay_driven"
    assert "against the reasons you've attached to them" in digest.content["monitoring_receipt"]
    assert "Would the same story still convince you today" in (digest.content["quiet_nudge"] or "")
