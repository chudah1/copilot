"""Tests for the valuation single-source-of-truth: GBP value, FX, and P&L."""
from unittest.mock import AsyncMock, patch

from app.models.holding import Holding
from app.services.valuation import (
    apply_broker_position,
    apply_market_price,
    compute_pnl,
    refresh_holding_price,
    to_account_value,
)

_VAL = "app.services.valuation"


def _holding(ticker="AAPL", quantity=10, avg_cost=100.0, currency=None):
    return Holding(
        ticker=ticker, name=ticker, quantity=quantity,
        average_cost_basis=avg_cost, currency=currency,
    )


# ── compute_pnl ──────────────────────────────────────────────────────────────

def test_compute_pnl_basic():
    pnl, pct = compute_pnl(1200.0, 10, 100.0)  # cost 1000, value 1200
    assert pnl == 200.0
    assert pct == 20.0


def test_compute_pnl_loss():
    pnl, pct = compute_pnl(800.0, 10, 100.0)
    assert pnl == -200.0
    assert pct == -20.0


def test_compute_pnl_none_value_is_unavailable_not_minus_100():
    # The whole point: no value must not render as -100%.
    assert compute_pnl(None, 10, 100.0) == (None, None)


def test_compute_pnl_zero_cost_is_unavailable():
    assert compute_pnl(500.0, 10, 0.0) == (None, None)


# ── FX conversion ────────────────────────────────────────────────────────────

async def test_to_account_value_applies_fx():
    with patch(f"{_VAL}.get_fx_rate", new_callable=AsyncMock, return_value=0.8):
        value = await to_account_value(10, 100.0, native_currency="USD")
    assert value == 800.0  # 10 * 100 * 0.8


async def test_to_account_value_none_price():
    assert await to_account_value(10, None, native_currency="USD") is None


async def test_apply_market_price_sets_native_price_and_gbp_value():
    holding = _holding(quantity=5)
    with patch(f"{_VAL}.get_fx_rate", new_callable=AsyncMock, return_value=0.8), patch(
        f"{_VAL}.detect_native_currency", return_value="USD"
    ):
        ok = await apply_market_price(holding, native_price=200.0)
    assert ok is True
    assert holding.current_price == 200.0          # native per share
    assert holding.current_value == 800.0          # 5 * 200 * 0.8, GBP
    assert holding.currency == "USD"


async def test_apply_market_price_no_price_returns_false():
    holding = _holding()
    assert await apply_market_price(holding, native_price=None) is False
    assert holding.current_value is None


async def test_refresh_holding_price_fetches_then_applies():
    holding = _holding(quantity=2, currency="USD")
    with patch(f"{_VAL}.fetch_live_price", new_callable=AsyncMock, return_value=300.0), patch(
        f"{_VAL}.get_fx_rate", new_callable=AsyncMock, return_value=0.5
    ):
        ok = await refresh_holding_price(holding)
    assert ok is True
    assert holding.current_value == 300.0  # 2 * 300 * 0.5


async def test_apply_broker_position_converts_cost_and_value_to_gbp():
    # The bug this fixes: broker native price/cost must land in GBP, not raw.
    holding = _holding(ticker="NVDA_US_EQ", quantity=4, avg_cost=0)
    with patch(f"{_VAL}.get_fx_rate", new_callable=AsyncMock, return_value=0.8), patch(
        f"{_VAL}.detect_native_currency", return_value="USD"
    ):
        await apply_broker_position(
            holding, quantity=4, native_price=150.0, native_avg_cost=100.0
        )
    assert holding.quantity == 4
    assert holding.average_cost_basis == 80.0       # 100 * 0.8, GBP
    assert holding.current_price == 150.0           # native
    assert holding.current_value == 480.0           # 4 * 150 * 0.8, GBP
    assert holding.currency == "USD"
