import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.monitoring_gap import MonitoringGap
from app.models.thesis import Thesis
from app.services.check_now import run_check_now
from app.services.market_data import CompanyData, MAX_CURRENT_TRANSCRIPT_AGE_DAYS


def _make_company_data(ticker="AAPL", current_price=120.0):
    return CompanyData(
        ticker=ticker,
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=current_price,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )


async def test_check_now_creates_monitoring_events(client, auth_headers, db, test_user, job_session_factory):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        must_remain_true="Revenue keeps growing.",
        what_would_change_my_mind="A major revenue miss.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Large moves."}
            ]
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(current_price=120.0)
    classification = type(
        "Classification", (), {"severity": "warning", "analysis": "Price moved."}
    )()

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.monitoring_pipeline.classify_event",
        new_callable=AsyncMock,
        return_value=classification,
    ), patch(
        # The background task opens its own session — in production that
        # session points at the real DB; in tests we redirect it to the
        # same TestSession factory the request handler uses so the BG task
        # can see the fixture-created holding + thesis rows.
        "app.services.check_now.async_session",
        job_session_factory,
    ):
        response = await client.post(
            f"/api/monitoring/holdings/{holding.id}/check-now",
            headers=auth_headers,
        )

    # Fresh check-now no longer runs synchronously — the pipeline is fired
    # as a BackgroundTask so a slow fresh run doesn't trip Cloudflare's edge
    # timeout. FastAPI TestClient still executes background tasks after the
    # response is emitted, so the DB state has landed by the time we assert.
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["events_created"] == 0

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(events) >= 1

    # The check stamps last_monitored_at so the dashboard can show "checked X ago".
    await db.refresh(holding)
    assert holding.last_monitored_at is not None


async def test_check_now_rate_limited_when_recent_event_exists(client, auth_headers, db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        confidence="high",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    # Create a recent event (within the 4-hour window)
    recent_event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="Review AAPL",
        summary="Price moved significantly.",
    )
    db.add(recent_event)
    await db.commit()

    response = await client.post(
        f"/api/monitoring/holdings/{holding.id}/check-now",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rate_limited"
    assert data["events_created"] == 0
    assert data["next_available_at"] is not None


async def test_check_now_returns_400_when_no_thesis(client, auth_headers, db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.commit()

    response = await client.post(
        f"/api/monitoring/holdings/{holding.id}/check-now",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No active thesis"


async def test_check_now_requires_auth(client, db):
    fake_id = uuid.uuid4()
    response = await client.post(f"/api/monitoring/holdings/{fake_id}/check-now")
    assert response.status_code in (401, 403)


async def test_run_check_now_returns_created_event_ids(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        must_remain_true="Revenue keeps growing.",
        what_would_change_my_mind="A major revenue miss.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Large moves."}
            ]
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(current_price=120.0)
    classification = type(
        "Classification", (), {"severity": "warning", "analysis": "Price moved."}
    )()

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ):
        with patch(
            "app.services.monitoring_pipeline.classify_event",
            new_callable=AsyncMock,
            return_value=classification,
        ):
            result = await run_check_now(holding, thesis, db)

    assert result.status == "completed"
    assert result.events_created == len(result.created_event_ids)
    assert result.created_event_ids
    assert all(event_id is not None for event_id in result.created_event_ids)


async def test_run_check_now_uses_broader_current_transcript_window(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        confidence="high",
        review_cadence_days=7,
        interpretation={"watch_hints": []},
        source="user",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(current_price=120.0)
    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.check_now.generate_monitoring_candidates",
        return_value=[],
    ) as mock_generate, patch(
        "app.services.check_now.load_active_decomposition",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.check_now.collect_news_evidence",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.check_now.filter_candidates",
        new_callable=AsyncMock,
        side_effect=lambda candidates, *args, **kwargs: candidates,
    ):
        result = await run_check_now(holding, thesis, db)

    assert result.status == "completed"
    assert mock_generate.call_args.kwargs["transcript_max_age_days"] == MAX_CURRENT_TRANSCRIPT_AGE_DAYS


async def test_run_check_now_uses_provisional_news_watches_without_decomposition(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="HIMS",
        name="Hims & Hers Health",
        quantity=10,
        average_cost_basis=20,
        current_price=20,
        current_value=200,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="GLP-1 growth remains intact.",
        must_remain_true="Compounded GLP-1 stays available long enough for a replacement path.",
        what_would_change_my_mind="FDA restricts compounded GLP-1 without a replacement path.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {
                    "kind": "news_watch",
                    "watch_for": "the FDA restricts compounded GLP-1 and the company fails to present a credible replacement path by next earnings",
                    "direction": "threatens",
                    "rationale": "This would hit the main growth driver.",
                }
            ]
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(ticker="HIMS", current_price=20.0)
    news_candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "FDA restricts compounded GLP-1 access",
        "evidence": {"headline": "FDA restricts compounded GLP-1 access", "summary": "Company has not outlined a replacement path."},
    }
    captured = {}

    async def _capture_news_watches(candidates, news_watches):
        captured["watches"] = news_watches
        return {}

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.check_now.load_active_decomposition",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.check_now.collect_news_evidence",
        new_callable=AsyncMock,
        return_value=[news_candidate],
    ), patch(
        "app.services.check_now.match_thesis_news_watches",
        new=_capture_news_watches,
    ), patch(
        "app.services.check_now.filter_candidates",
        new_callable=AsyncMock,
        side_effect=lambda candidates, *args, **kwargs: candidates,
    ), patch(
        "app.services.check_now.classify_candidates_for_thesis",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.check_now.persist_classified_candidates",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await run_check_now(holding, thesis, db)

    assert result.status == "completed"
    assert len(captured["watches"]) == 1
    assert captured["watches"][0].signal_id is None
    assert "compounded GLP-1" in captured["watches"][0].watch_for


async def test_run_check_now_skips_unlinked_analyst_revision_and_unlinked_earnings_surprises(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Data center demand stays strong.",
        must_remain_true="Revenue growth stays high.",
        what_would_change_my_mind="Demand rolls over.",
        confidence="high",
        review_cadence_days=7,
        interpretation={"watch_hints": []},
        source="user",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(ticker="NVDA", current_price=120.0)
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was -15.1%.",
            "evidence": {"recent_earnings_surprise_pct": -15.1},
        },
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was 5.6%.",
            "evidence": {"recent_earnings_surprise_pct": 5.6},
        },
        {
            "event_type": "analyst_revision",
            "description": "10 net analyst upgrades in the past 30 days.",
            "evidence": {"analyst_revision_id": "NVDA", "net_changes_30d": 10},
        },
    ]

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.check_now.generate_monitoring_candidates",
        return_value=candidates,
    ), patch(
        "app.services.check_now.load_active_decomposition",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.check_now.collect_news_evidence",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.check_now.filter_candidates",
        new_callable=AsyncMock,
        side_effect=lambda candidates, *args, **kwargs: candidates,
    ):
        result = await run_check_now(holding, thesis, db)

    assert result.status == "completed"
    assert result.events_created == 0

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert events == []


async def test_run_check_now_skips_unlinked_neutral_news_like_candidates(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="AMD",
        name="Advanced Micro Devices",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI sentiment should keep helping the stock.",
        must_remain_true="The company stays in favorable AI conversations.",
        what_would_change_my_mind="The company falls out of favor.",
        confidence="medium",
        review_cadence_days=7,
        interpretation={"watch_hints": []},
        source="user",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(ticker="AMD", current_price=120.0)
    candidates = [
        {
            "event_type": "contract_renewal_update",
            "description": "A multi-stock roundup mentioned AMD alongside several unrelated companies.",
            "evidence": {
                "headline": "5 Stocks Investors Couldn't Stop Buzzing About This Week",
                "summary": "This roundup mentioned AMD among several names but did not tie it to a thesis signal.",
            },
        },
    ]

    classification = type("Classification", (), {"severity": "info", "analysis": "Generic mention only."})()

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.check_now.generate_monitoring_candidates",
        return_value=candidates,
    ), patch(
        "app.services.check_now.load_active_decomposition",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.check_now.collect_news_evidence",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.check_now.filter_candidates",
        new_callable=AsyncMock,
        side_effect=lambda candidates, *args, **kwargs: candidates,
    ), patch(
        "app.services.monitoring_pipeline.classify_event",
        new_callable=AsyncMock,
        return_value=classification,
    ):
        result = await run_check_now(holding, thesis, db)

    assert result.status == "completed"
    assert result.events_created == 0

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert events == []


async def test_check_now_records_gemini_failure_as_monitoring_gap(db, test_user):
    """The walkthrough on 2026-06-15 found Gemini 429s during check-now were
    silently swallowed — the user got thinner evidence with no visibility into
    why. Mirror the daily-job behavior: a Gemini failure during a user-
    initiated check writes a monitoring_gap row tagged with source='gemini_news'."""
    holding = Holding(
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        sector="Technology",
        quantity=10,
        average_cost_basis=100.0,
        current_price=200.0,
        current_value=2000.0,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI GPU dominance.",
        confidence="high",
        review_cadence_days=7,
        interpretation={},
        source="user",
    )
    db.add(thesis)
    await db.commit()

    company_data = _make_company_data(ticker="NVDA", current_price=200.0)

    with patch(
        "app.services.check_now.fetch_company_data",
        new_callable=AsyncMock,
        return_value=company_data,
    ), patch(
        "app.services.check_now.load_active_decomposition",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.check_now.collect_news_evidence",
        new_callable=AsyncMock,
        side_effect=RuntimeError("429 RESOURCE_EXHAUSTED prepayment credits depleted"),
    ), patch(
        "app.services.check_now.match_thesis_news_watches",
        new_callable=AsyncMock,
        return_value={},
    ), patch(
        "app.services.check_now.filter_candidates",
        new_callable=AsyncMock,
        side_effect=lambda candidates, *args, **kwargs: candidates,
    ), patch(
        "app.services.check_now.classify_candidates_for_thesis",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.services.check_now.persist_classified_candidates",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = await run_check_now(holding, thesis, db)

    # check-now should not crash on a Gemini failure — it just loses that
    # candidate source.
    assert result.status == "completed"

    # A monitoring_gap row should now exist for this thesis with the right
    # source and a non-empty error message.
    gaps = (
        await db.execute(
            MonitoringGap.__table__.select().where(MonitoringGap.thesis_id == thesis.id)
        )
    ).all()
    assert len(gaps) == 1, f"Expected one gap row, got {len(gaps)}"
    gap = gaps[0]
    assert gap.source == "gemini_news"
    assert "RESOURCE_EXHAUSTED" in gap.error_message
    assert gap.run_id.startswith("check_now:")
