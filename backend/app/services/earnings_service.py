"""Earnings calendar caching service.

Reads/writes from the earnings_calendar table so we don't hit yfinance
on every API request. Entries are considered stale after 7 days.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.earnings_calendar import EarningsCalendar

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 7


def _is_stale(entry: EarningsCalendar) -> bool:
    report_date = entry.report_date
    if report_date is not None:
        normalized_report = report_date if report_date.tzinfo is not None else report_date.replace(tzinfo=timezone.utc)
        if normalized_report.date() < datetime.now(timezone.utc).date():
            return True

    last = entry.last_refreshed_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).days >= STALE_AFTER_DAYS


async def get_or_refresh_earnings(
    db: AsyncSession,
    ticker: str,
) -> datetime | None:
    """Return the next earnings date for a ticker, refreshing the cache if stale."""
    result = await db.execute(
        select(EarningsCalendar).where(EarningsCalendar.ticker == ticker.upper())
    )
    entry = result.scalar_one_or_none()

    if entry is not None and not _is_stale(entry):
        return entry.report_date

    # Refresh from market data
    report_date = await _fetch_earnings_date(ticker)
    now = datetime.now(timezone.utc)

    try:
        async with db.begin_nested():
            if entry is None:
                entry = EarningsCalendar(
                    ticker=ticker.upper(),
                    report_date=report_date,
                    source="yfinance",
                    last_refreshed_at=now,
                )
                db.add(entry)
            else:
                entry.report_date = report_date
                entry.last_refreshed_at = now
    except Exception as exc:
        logger.warning("Could not persist earnings cache for %s: %s", ticker, exc)

    return report_date


async def refresh_earnings_batch(db: AsyncSession, tickers: list[str]) -> None:
    """Refresh earnings cache for a batch of tickers regardless of staleness."""
    now = datetime.now(timezone.utc)
    for ticker in tickers:
        ticker_upper = ticker.upper()
        try:
            report_date = await _fetch_earnings_date(ticker_upper)
            result = await db.execute(
                select(EarningsCalendar).where(EarningsCalendar.ticker == ticker_upper)
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                db.add(EarningsCalendar(
                    ticker=ticker_upper,
                    report_date=report_date,
                    source="yfinance",
                    last_refreshed_at=now,
                ))
            else:
                entry.report_date = report_date
                entry.last_refreshed_at = now
        except Exception as exc:
            logger.warning("Failed to refresh earnings for %s: %s", ticker_upper, exc)
    await db.flush()


async def _fetch_earnings_date(ticker: str) -> datetime | None:
    """Fetch the next earnings date from the market data provider."""
    from app.services.market_data import fetch_company_data
    try:
        company_data = await fetch_company_data(ticker)
        return company_data.upcoming_earnings_date
    except Exception as exc:
        logger.warning("Could not fetch earnings date for %s: %s", ticker, exc)
        return None
