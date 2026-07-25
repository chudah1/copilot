from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import httpx

from app.models.holding import Holding
from app.models.user import User
from app.schemas.holding import HoldingResponse
from app.services.market_data import get_fx_rate_optional

logger = logging.getLogger(__name__)

ACCOUNT_CURRENCY = "GBP"
DEFAULT_PORTFOLIO_CURRENCY = ACCOUNT_CURRENCY
ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

# The ECB covers most of these directly. The remaining currencies use the
# yfinance fallback selected for the product.
SUPPORTED_PORTFOLIO_CURRENCIES = frozenset(
    {
        "AED",
        "AUD",
        "BRL",
        "CAD",
        "CHF",
        "CNY",
        "CZK",
        "DKK",
        "EUR",
        "GBP",
        "GHS",
        "HKD",
        "HUF",
        "IDR",
        "ILS",
        "INR",
        "ISK",
        "JPY",
        "KES",
        "KRW",
        "MXN",
        "MYR",
        "NGN",
        "NOK",
        "NZD",
        "PHP",
        "PLN",
        "RON",
        "SAR",
        "SEK",
        "SGD",
        "THB",
        "TRY",
        "USD",
        "ZAR",
    }
)

_ECB_REFRESH_AFTER = timedelta(hours=12)
_ECB_REQUEST_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class FXQuote:
    rate: float
    source: str
    as_of: datetime


@dataclass(frozen=True)
class DisplayCurrencyContext:
    requested_currency: str
    portfolio_currency: str
    rate_from_gbp: float
    source: str
    as_of: datetime
    fx_unavailable: bool = False

    def convert_from_gbp(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value) * self.rate_from_gbp, 2)


@dataclass
class _ECBCache:
    rates_per_eur: dict[str, float]
    as_of: datetime
    fetched_at: datetime


_ecb_cache: _ECBCache | None = None
_ecb_lock = asyncio.Lock()


def normalize_portfolio_currency(value: object) -> str:
    if not isinstance(value, str):
        return DEFAULT_PORTFOLIO_CURRENCY
    currency = value.strip().upper()
    return currency if currency in SUPPORTED_PORTFOLIO_CURRENCIES else DEFAULT_PORTFOLIO_CURRENCY


def get_preferred_portfolio_currency(user: User) -> str:
    return normalize_portfolio_currency((user.preferences or {}).get("portfolio_currency"))


def _parse_ecb_rates(xml_text: str) -> tuple[dict[str, float], datetime]:
    root = ElementTree.fromstring(xml_text)
    rates: dict[str, float] = {"EUR": 1.0}
    rate_date: datetime | None = None

    for node in root.iter():
        currency = node.attrib.get("currency")
        raw_rate = node.attrib.get("rate")
        if currency and raw_rate:
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                continue
            if rate > 0:
                rates[currency.upper()] = rate

        raw_date = node.attrib.get("time")
        if raw_date and rate_date is None:
            try:
                rate_date = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    if len(rates) == 1:
        raise ValueError("ECB response did not contain exchange rates")

    return rates, rate_date or datetime.now(timezone.utc)


async def _fetch_ecb_rates() -> _ECBCache:
    async with httpx.AsyncClient(timeout=_ECB_REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            ECB_DAILY_RATES_URL,
            headers={"User-Agent": "PenKeep/1.0"},
        )
        response.raise_for_status()
    rates, as_of = _parse_ecb_rates(response.text)
    return _ECBCache(
        rates_per_eur=rates,
        as_of=as_of,
        fetched_at=datetime.now(timezone.utc),
    )


async def _get_ecb_rates() -> _ECBCache | None:
    global _ecb_cache

    now = datetime.now(timezone.utc)
    if _ecb_cache and now - _ecb_cache.fetched_at < _ECB_REFRESH_AFTER:
        return _ecb_cache

    async with _ecb_lock:
        now = datetime.now(timezone.utc)
        if _ecb_cache and now - _ecb_cache.fetched_at < _ECB_REFRESH_AFTER:
            return _ecb_cache
        try:
            _ecb_cache = await _fetch_ecb_rates()
        except Exception:
            logger.warning("ECB FX lookup failed; trying the last-known rate or yfinance", exc_info=True)
        return _ecb_cache


async def get_fx_quote(from_currency: str, to_currency: str) -> FXQuote | None:
    from_currency = from_currency.strip().upper()
    to_currency = to_currency.strip().upper()
    now = datetime.now(timezone.utc)
    if from_currency == to_currency:
        return FXQuote(rate=1.0, source="identity", as_of=now)

    ecb = await _get_ecb_rates()
    if ecb:
        from_rate = ecb.rates_per_eur.get(from_currency)
        to_rate = ecb.rates_per_eur.get(to_currency)
        if from_rate and to_rate:
            return FXQuote(
                rate=to_rate / from_rate,
                source="ecb",
                as_of=ecb.as_of,
            )

    fallback = await get_fx_rate_optional(from_currency, to_currency)
    if fallback and fallback > 0:
        return FXQuote(rate=fallback, source="yfinance", as_of=now)
    return None


async def get_display_currency_context(user: User) -> DisplayCurrencyContext:
    requested = get_preferred_portfolio_currency(user)
    quote = await get_fx_quote(ACCOUNT_CURRENCY, requested)
    if quote is None:
        # Keep the values correct and label them as GBP. The response also tells
        # the frontend that the user's requested conversion is unavailable.
        return DisplayCurrencyContext(
            requested_currency=requested,
            portfolio_currency=ACCOUNT_CURRENCY,
            rate_from_gbp=1.0,
            source="unavailable",
            as_of=datetime.now(timezone.utc),
            fx_unavailable=requested != ACCOUNT_CURRENCY,
        )
    return DisplayCurrencyContext(
        requested_currency=requested,
        portfolio_currency=requested,
        rate_from_gbp=quote.rate,
        source=quote.source,
        as_of=quote.as_of,
    )


def serialize_holding(holding: Holding, context: DisplayCurrencyContext) -> HoldingResponse:
    return HoldingResponse(
        id=holding.id,
        ticker=holding.ticker,
        name=holding.name,
        exchange=holding.exchange,
        quantity=float(holding.quantity),
        average_cost_basis=context.convert_from_gbp(float(holding.average_cost_basis)) or 0.0,
        average_cost_native=(
            float(holding.average_cost_native)
            if holding.average_cost_native is not None
            else None
        ),
        currency=holding.currency,
        current_price=float(holding.current_price) if holding.current_price is not None else None,
        current_value=context.convert_from_gbp(
            float(holding.current_value) if holding.current_value is not None else None
        ),
        portfolio_currency=context.portfolio_currency,
        preferred_currency=context.requested_currency,
        fx_unavailable=context.fx_unavailable,
        sector=holding.sector,
        geography=holding.geography,
        asset_class=holding.asset_class,
        last_updated_at=holding.last_updated_at,
    )


def serialize_holdings(
    holdings: list[Holding],
    context: DisplayCurrencyContext,
) -> list[HoldingResponse]:
    return [serialize_holding(holding, context) for holding in holdings]
