import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.thesis import Thesis
from tests.conftest import engine


@pytest.mark.asyncio
async def test_summary_creates_snapshot_lazily(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1600, user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    resp = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert resp.status_code == 200

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM portfolio_snapshots WHERE user_id = :uid"),
            {"uid": str(test_user.id)},
        )
        assert result.scalar() >= 1


@pytest.mark.asyncio
async def test_summary_does_not_duplicate_snapshot(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1600, user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    resp1 = await client.get("/api/portfolio/summary", headers=auth_headers)
    resp2 = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_summary_survives_snapshot_lock_contention(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1600, user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    with patch(
        "app.routes.portfolio.AsyncSession.commit",
        side_effect=OperationalError("INSERT INTO portfolio_snapshots", {}, Exception("database is locked")),
    ):
        resp = await client.get("/api/portfolio/summary", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["holdings_count"] == 1


@pytest.mark.asyncio
async def test_trend_returns_previous_snapshot(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1600, user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    # Create snapshot for today via summary
    resp = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert resp.status_code == 200

    # Now query trend but pretend it's tomorrow — today's snapshot becomes "previous"
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    with patch("app.routes.portfolio.datetime") as mock_dt:
        mock_dt.now.return_value = tomorrow
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        resp2 = await client.get("/api/portfolio/summary/trend", headers=auth_headers)

    assert resp2.status_code == 200
    data = resp2.json()
    # Snapshot was created with UTC date, which may differ from local date
    utc_today = datetime.now(timezone.utc).date()
    assert data["snapshot_date"] == utc_today.isoformat()
    assert data["holdings_count"] == 1


@pytest.mark.asyncio
async def test_trend_counts_events_from_the_snapshot_date_only(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="NOW", name="ServiceNow",
        quantity=2, average_cost_basis=600, currency="GBP",
        current_value=1300, user_id=test_user.id,
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Subscription growth", confidence="medium",
    )
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    snapshot = PortfolioSnapshot(
        id=uuid.uuid4(), user_id=test_user.id, snapshot_date=yesterday,
        total_value=1300, total_cost=1200, top_3_concentration_pct=100,
        thesis_coverage_pct=100, monitorable_pct=100,
        unmonitored_count=0, holdings_count=1,
    )
    db.add_all([holding, thesis, snapshot])
    await db.commit()

    snapshot_start = datetime.combine(yesterday, datetime.min.time(), tzinfo=timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="info", verdict="supports",
            title="New evidence", summary="Created after the comparison snapshot.",
            created_at=snapshot_start + timedelta(hours=1),
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Old evidence", summary="Created before the comparison snapshot.",
            created_at=snapshot_start - timedelta(seconds=1),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/summary/trend", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_date"] == yesterday.isoformat()
    assert data["new_event_count"] == 1


@pytest.mark.asyncio
async def test_trend_returns_empty_when_no_history(client, auth_headers):
    resp = await client.get("/api/portfolio/summary/trend", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_date"] is None
    assert data["top_3_concentration_pct"] is None


@pytest.mark.asyncio
async def test_trend_excludes_today_snapshot(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        current_value=1600, user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    resp = await client.get("/api/portfolio/summary", headers=auth_headers)
    assert resp.status_code == 200

    resp2 = await client.get("/api/portfolio/summary/trend", headers=auth_headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["snapshot_date"] is None
