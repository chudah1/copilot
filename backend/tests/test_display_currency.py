from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from app.models.holding import Holding
from app.services.display_currency import (
    DisplayCurrencyContext,
    FXQuote,
    _ECBCache,
    _parse_ecb_rates,
    get_fx_quote,
    serialize_holding,
)


def test_parse_ecb_rates_reads_daily_table():
    xml = """<?xml version="1.0"?>
    <gesmes:Envelope
      xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
      xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
      <Cube>
        <Cube time="2026-07-24">
          <Cube currency="USD" rate="1.1700"/>
          <Cube currency="GBP" rate="0.8700"/>
        </Cube>
      </Cube>
    </gesmes:Envelope>
    """

    rates, as_of = _parse_ecb_rates(xml)

    assert rates == {"EUR": 1.0, "USD": 1.17, "GBP": 0.87}
    assert as_of == datetime(2026, 7, 24, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fx_quote_uses_ecb_cross_rate_before_yfinance():
    now = datetime.now(timezone.utc)
    table = _ECBCache(
        rates_per_eur={"EUR": 1.0, "GBP": 0.8, "USD": 1.2},
        as_of=now,
        fetched_at=now,
    )

    with patch(
        "app.services.display_currency._get_ecb_rates",
        new_callable=AsyncMock,
        return_value=table,
    ), patch(
        "app.services.display_currency.get_fx_rate_optional",
        new_callable=AsyncMock,
    ) as fallback:
        quote = await get_fx_quote("GBP", "USD")

    assert quote is not None
    assert quote.rate == pytest.approx(1.5)
    assert quote.source == "ecb"
    fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_fx_quote_falls_back_to_yfinance_for_non_ecb_currency():
    now = datetime.now(timezone.utc)
    table = _ECBCache(
        rates_per_eur={"EUR": 1.0, "GBP": 0.8},
        as_of=now,
        fetched_at=now,
    )

    with patch(
        "app.services.display_currency._get_ecb_rates",
        new_callable=AsyncMock,
        return_value=table,
    ), patch(
        "app.services.display_currency.get_fx_rate_optional",
        new_callable=AsyncMock,
        return_value=2100.0,
    ):
        quote = await get_fx_quote("GBP", "NGN")

    assert quote is not None
    assert quote.rate == 2100.0
    assert quote.source == "yfinance"


def test_serialize_holding_converts_display_values_without_mutating_storage():
    now = datetime.now(timezone.utc)
    holding = Holding(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        average_cost_native=125,
        currency="USD",
        current_price=150,
        current_value=1200,
        last_updated_at=now,
    )
    context = DisplayCurrencyContext(
        requested_currency="EUR",
        portfolio_currency="EUR",
        rate_from_gbp=1.25,
        source="ecb",
        as_of=now,
    )

    response = serialize_holding(holding, context)

    assert response.average_cost_basis == 125
    assert response.current_value == 1500
    assert response.current_price == 150
    assert response.currency == "USD"
    assert response.portfolio_currency == "EUR"
    assert float(holding.average_cost_basis) == 100
    assert float(holding.current_value) == 1200


def test_unavailable_context_reports_actual_gbp_values():
    now = datetime.now(timezone.utc)
    context = DisplayCurrencyContext(
        requested_currency="GHS",
        portfolio_currency="GBP",
        rate_from_gbp=1.0,
        source="unavailable",
        as_of=now,
        fx_unavailable=True,
    )

    assert context.convert_from_gbp(42.5) == 42.5
    assert context.portfolio_currency == "GBP"
    assert context.requested_currency == "GHS"
    assert context.fx_unavailable is True
