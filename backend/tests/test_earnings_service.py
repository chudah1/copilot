from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.earnings_calendar import EarningsCalendar
from app.services.earnings_service import get_or_refresh_earnings


@pytest.mark.asyncio
async def test_get_or_refresh_earnings_reuses_fresh_future_entry(db):
    future_date = datetime.now(timezone.utc) + timedelta(days=5)
    entry = EarningsCalendar(
        ticker="AAPL",
        report_date=future_date,
        source="test",
        last_refreshed_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()

    with patch("app.services.earnings_service._fetch_earnings_date", new_callable=AsyncMock) as mock_fetch:
        report_date = await get_or_refresh_earnings(db, "AAPL")

    assert report_date == future_date
    mock_fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_refresh_earnings_refreshes_recent_past_entry(db):
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    next_quarter = datetime.now(timezone.utc) + timedelta(days=60)
    entry = EarningsCalendar(
        ticker="AAPL",
        report_date=yesterday,
        source="test",
        last_refreshed_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()

    with patch("app.services.earnings_service._fetch_earnings_date", new_callable=AsyncMock, return_value=next_quarter) as mock_fetch:
        report_date = await get_or_refresh_earnings(db, "AAPL")

    assert report_date == next_quarter
    mock_fetch.assert_awaited_once()
    refreshed = (await db.execute(select(EarningsCalendar).where(EarningsCalendar.ticker == "AAPL"))).scalar_one()
    assert refreshed.report_date == next_quarter
