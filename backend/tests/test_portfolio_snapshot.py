import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
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
