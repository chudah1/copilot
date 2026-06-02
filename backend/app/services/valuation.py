"""Single source of truth for valuing a holding in the account currency (GBP).

Before this module, value/FX/P&L were recomputed in six places with subtly
different rules — two of them (monitoring_run, portfolio_sync) skipped the FX
conversion entirely and wrote a foreign-currency number into a GBP field. For a
product whose whole job is to show truthful numbers, that is the most dangerous
class of bug. Every place that sets a holding's value or computes P&L now goes
through here.

Conventions (must hold everywhere):
- holding.current_price  -> latest price per share in the instrument's NATIVE
  currency (informational).
- holding.current_value  -> market value in the ACCOUNT currency (GBP).
- holding.average_cost_basis -> per-share cost in the ACCOUNT currency (GBP).
- holding.currency -> the instrument's native currency (ISO 4217).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.market_data import detect_native_currency, fetch_live_price, get_fx_rate

ACCOUNT_CURRENCY = "GBP"


async def account_fx_rate(native_currency: str | None, ticker: str | None) -> tuple[float, str]:
    """FX multiplier from a holding's native currency to the account currency,
    plus the resolved native currency. Falls back to the ticker-suffix heuristic
    then to the account currency (rate 1.0)."""
    ccy = native_currency or (detect_native_currency(ticker) if ticker else None) or ACCOUNT_CURRENCY
    fx = await get_fx_rate(ccy, ACCOUNT_CURRENCY)
    return fx, ccy


async def to_account_value(
    quantity,
    native_price,
    *,
    native_currency: str | None = None,
    ticker: str | None = None,
) -> float | None:
    """Market value of `quantity` shares priced at `native_price`, in GBP."""
    if native_price is None or quantity is None:
        return None
    fx, _ = await account_fx_rate(native_currency, ticker)
    return round(float(quantity) * float(native_price) * fx, 2)


async def apply_market_price(
    holding,
    *,
    native_price,
    native_currency: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Set current_price (native) + current_value (GBP) + currency on a holding
    from a freshly fetched native price. Returns False if there's no price."""
    if native_price is None:
        return False
    fx, ccy = await account_fx_rate(native_currency or holding.currency, holding.ticker)
    holding.current_price = float(native_price)
    holding.current_value = round(float(holding.quantity) * float(native_price) * fx, 2)
    holding.currency = ccy
    holding.last_updated_at = now or datetime.now(timezone.utc)
    return True


async def refresh_holding_price(holding, *, now: datetime | None = None) -> bool:
    """Fetch the latest market price and revalue the holding. The canonical way
    to bring a single holding's price up to date."""
    price = await fetch_live_price(holding.ticker)
    return await apply_market_price(holding, native_price=price, now=now)


async def apply_broker_position(
    holding,
    *,
    quantity,
    native_price,
    native_avg_cost,
    native_currency: str | None = None,
    now: datetime | None = None,
) -> None:
    """Set all valuation fields from a broker position whose price and average
    cost are quoted in the instrument's native currency. Converts both the cost
    basis and the market value into GBP so they're consistent with the rest of
    the system (the bug portfolio_sync used to have)."""
    fx, ccy = await account_fx_rate(native_currency, holding.ticker)
    holding.quantity = quantity
    holding.average_cost_basis = round(float(native_avg_cost) * fx, 4)
    holding.currency = ccy
    if native_price is not None:
        holding.current_price = float(native_price)
        holding.current_value = round(float(quantity) * float(native_price) * fx, 2)
    holding.last_updated_at = now or datetime.now(timezone.utc)


def compute_pnl(value_gbp, quantity, average_cost_basis_gbp) -> tuple[float | None, float | None]:
    """Unrealised P&L and P&L% in the account currency. cost = quantity * cost
    basis (both already GBP). Returns (None, None) when value or cost is unusable
    — callers must render "unavailable", never a misleading 0 / -100%."""
    if value_gbp is None or quantity is None or average_cost_basis_gbp is None:
        return None, None
    cost = float(quantity) * float(average_cost_basis_gbp)
    if cost <= 0:
        return None, None
    pnl = float(value_gbp) - cost
    return round(pnl, 2), round(pnl / cost * 100, 2)
