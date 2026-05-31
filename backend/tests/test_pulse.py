import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis


@pytest.mark.asyncio
async def test_pulse_no_holdings(client, auth_headers):
    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pulses"] == []
    assert data["next_digest_at"] is not None


@pytest.mark.asyncio
async def test_pulse_holding_without_thesis(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "review"
    assert pulses[0]["has_thesis"] is False
    assert pulses[0]["urgency_score"] == 100


@pytest.mark.asyncio
async def test_pulse_intact_thesis_no_events(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "intact"
    assert pulses[0]["has_thesis"] is True


@pytest.mark.asyncio
async def test_pulse_last_checked_reflects_monitored_at_without_events(
    client, auth_headers, test_user, db: AsyncSession
):
    # A quiet first pulse creates no event but stamps last_monitored_at — the
    # dashboard must still be able to say "checked X ago", not leave it blank.
    checked_at = datetime.now(timezone.utc) - timedelta(hours=2)
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id, last_monitored_at=checked_at,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "intact"
    assert pulses[0]["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_pulse_review_on_breaking_event(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="metric_threshold", severity="thesis_breaking",
        title="Revenue declined", summary="Revenue growth turned negative.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "review"


@pytest.mark.asyncio
async def test_pulse_watch_on_warning_event(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="MSFT", name="Microsoft",
        quantity=5, average_cost_basis=300, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Cloud dominance", confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="news_or_earnings_candidate", severity="warning",
        title="Azure growth slowing", summary="Azure growth decelerated to 22%.",
        ai_analysis="Azure growth is being tested after the slowdown. Review whether the cloud thesis still holds.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "watch"
    assert pulses[0]["assumption_label"] == "Azure growth slowing"
    assert pulses[0]["latest_event_summary"] == "Azure growth is being tested after the slowdown. Review whether the cloud thesis still holds."
    assert pulses[0]["latest_event_at"] is not None
    assert pulses[0]["urgency_score"] > 55


@pytest.mark.asyncio
async def test_pulse_batches_same_day_events_into_one_summary(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="NVDA", name="NVIDIA",
        quantity=4, average_cost_basis=800, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI infrastructure demand", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    now = datetime.now(timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="earnings_surprise", severity="warning",
            title="Earnings beat", summary="Revenue beat expectations.",
            evidence_type="earnings_surprise",
            created_at=now,
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="earnings_call_transcript", severity="warning",
            title="Transcript review", summary="Management highlighted supply constraints.",
            evidence_type="earnings_call_transcript",
            created_at=now - timedelta(hours=1),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["recent_event_count"] == 2
    assert pulse["latest_event_summary"].startswith("2 new signals today:")


@pytest.mark.asyncio
async def test_pulse_respects_zero_current_value_for_pnl(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="XYZ", name="Example Co",
        quantity=10, average_cost_basis=100, current_value=0, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Turnaround bet", confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pnl_pct"] == -100.0


@pytest.mark.asyncio
async def test_pulse_stale_thesis_uses_review_cadence_for_watch_status(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="SHOP", name="Shopify",
        quantity=3, average_cost_basis=70, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Commerce platform compounding", confidence="medium",
        review_cadence_days=30,
        updated_at=datetime.now(timezone.utc) - timedelta(days=52),
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "watch"
    assert pulse["reason"] == "This thesis is 52 days old and 22 days past its review cadence."
    assert pulse["urgency_score"] > 55


@pytest.mark.asyncio
async def test_pulse_stale_high_confidence_thesis_can_escalate_to_review(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="TSM", name="TSMC",
        quantity=6, average_cost_basis=90, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Foundry leadership", confidence="high",
        review_cadence_days=30,
        updated_at=datetime.now(timezone.utc) - timedelta(days=108),
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "review"
    assert pulse["reason"] == "This thesis is 108 days old and far past its 30-day review cadence."
    assert pulse["urgency_score"] >= 90
