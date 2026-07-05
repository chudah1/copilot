from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
API_NINJAS_TRANSCRIPT_URL = "https://api.api-ninjas.com/v1/earningstranscript"

# Cache TTLs in seconds
_CACHE_TTL_LONG = 24 * 3600   # overview, earnings, earnings_calendar — change quarterly
_CACHE_TTL_SHORT = 4 * 3600   # quote, news — change frequently


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class _TTLCache:
    """Simple in-memory TTL cache for Alpha Vantage responses."""

    def __init__(self) -> None:
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None or time.monotonic() > entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float) -> None:
        self._store[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl)

    def clear(self) -> None:
        self._store.clear()


_cache = _TTLCache()


# Trading 212 exchange code (trailing letter before _EQ) → Yahoo Finance suffix.
# T212 format: {BASE}{EXCHANGE_CODE}_EQ  e.g. ASMLA_EQ = ASML on Amsterdam.
# US stocks use _US_EQ (no exchange code suffix needed).
_T212_EXCHANGE_SUFFIXES: dict[str, str] = {
    "A": ".AS",   # Euronext Amsterdam
    "L": ".L",    # London Stock Exchange
    "P": ".PA",   # Euronext Paris
    "X": ".DE",   # Xetra (Frankfurt)
    "I": ".MI",   # Borsa Italiana (Milan)
    "E": ".MC",   # Bolsa de Madrid
    "S": ".ST",   # Nasdaq Stockholm
    "C": ".CO",   # Nasdaq Copenhagen
    "H": ".HE",   # Nasdaq Helsinki
    "W": ".VI",   # Wiener Börse (Vienna)
    "B": ".BR",   # Euronext Brussels
    "Z": ".SW",   # SIX Swiss Exchange
    "N": ".OL",   # Oslo Børs
    "T": ".T",    # Tokyo Stock Exchange
}

# Trading 212 exchange code → native trading currency (ISO 4217).
_T212_EXCHANGE_CURRENCIES: dict[str, str] = {
    "A": "EUR",   # Euronext Amsterdam
    "L": "GBP",   # London Stock Exchange
    "P": "EUR",   # Euronext Paris
    "X": "EUR",   # Xetra (Frankfurt)
    "I": "EUR",   # Borsa Italiana (Milan)
    "E": "EUR",   # Bolsa de Madrid
    "S": "SEK",   # Nasdaq Stockholm
    "C": "DKK",   # Nasdaq Copenhagen
    "H": "EUR",   # Nasdaq Helsinki
    "W": "EUR",   # Wiener Börse (Vienna)
    "B": "EUR",   # Euronext Brussels
    "Z": "CHF",   # SIX Swiss Exchange
    "N": "NOK",   # Oslo Børs
    "T": "JPY",   # Tokyo Stock Exchange
}


def _normalize_ticker(ticker: str) -> str:
    """Convert a Trading 212 ticker to a Yahoo Finance / Alpha Vantage symbol.

    T212 formats:
        NVDA_US_EQ  → NVDA          (US equity, no exchange suffix needed)
        ASMLA_EQ    → ASML.AS       (Amsterdam: trailing A maps to .AS)
        ASMLa_EQ    → ASML.AS       (same, lowercase variant)
        VODL_EQ     → VOD.L         (London)
        UNKNOWN_EQ  → UNKNOWN       (unrecognised code — fetcher retries)
    """
    upper = ticker.upper()

    # US equities: strip _US_EQ, base ticker is already clean.
    if upper.endswith("_US_EQ"):
        return upper[: -len("_US_EQ")]

    # Non-US equities: last letter before _EQ is the T212 exchange code.
    if upper.endswith("_EQ"):
        base_with_code = upper[: -len("_EQ")]       # e.g. "ASMLA"
        if len(base_with_code) >= 2:
            base = base_with_code[:-1]               # e.g. "ASML"
            code = base_with_code[-1]                # e.g. "A"
            suffix = _T212_EXCHANGE_SUFFIXES.get(code)
            if suffix:
                return f"{base}{suffix}"             # e.g. "ASML.AS"
            # Unknown exchange code — return base without suffix.
            # _fetch_yfinance_company_data will retry with last char stripped.
            return base_with_code

    # Already a clean ticker (or an unseen format) — return as-is.
    return ticker


def _normalize_currency(code: str | None) -> str | None:
    """Normalise a provider-reported currency code to ISO 4217.

    yfinance reports London-listed instruments as "GBp" (pence). For currency
    *labelling* we fold that to "GBP"; price-in-pence scaling is handled
    elsewhere. Returns None for empty/unknown input so callers can fall back.
    """
    if not code:
        return None
    normalized = code.strip().upper()
    return normalized or None


def detect_native_currency(ticker: str) -> str:
    """Best-effort ISO 4217 currency for a T212 ticker, inferred from its suffix.

    This is a HEURISTIC fallback used only when the data provider's authoritative
    currency (CompanyData.currency / Holding.currency) is unavailable. The T212
    suffix cases are deterministic and reliable:
        NVDA_US_EQ  → "USD"
        ASMLA_EQ    → "EUR"  (Amsterdam)
        VODL_EQ     → "GBP"  (London)
        NOVOL_EQ    → "NOK"  (Oslo)
    A bare/clean ticker (e.g. "ASML" typed into research) carries NO exchange
    information, so we cannot know its currency here — prefer the provider value
    upstream. The final "GBP" return is a last-resort guess for manual LSE
    holdings and will be wrong for clean US tickers; do not rely on it when a
    provider currency is available.
    """
    upper = ticker.upper()
    if upper.endswith("_US_EQ"):
        return "USD"
    if upper.endswith("_EQ"):
        base_with_code = upper[:-3]          # strip "_EQ"
        if len(base_with_code) >= 2:
            code = base_with_code[-1]
            return _T212_EXCHANGE_CURRENCIES.get(code, "USD")
    return "GBP"


_CACHE_TTL_PRICE = 60  # live price — refresh every minute


def _yfinance_fast_price_sync(ticker: str) -> float | None:
    """Blocking call — fetch current price via fast_info (lightweight, no heavy info call)."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        price = t.fast_info.last_price
        return float(price) if price else None
    except Exception:
        return None


def _yfinance_close_on_sync(ticker: str, when: datetime) -> float | None:
    """Blocking call — the closing price on/nearest-before `when` via history."""
    import yfinance as yf

    try:
        hist = yf.Ticker(ticker).history(
            start=(when - timedelta(days=7)).date(),
            end=(when + timedelta(days=1)).date(),
        )
        if hist is None or hist.empty:
            return None
        closes = hist["Close"].dropna()
        return float(closes.iloc[-1]) if not closes.empty else None
    except Exception:
        return None


async def fetch_price_on(ticker: str, when: datetime) -> float | None:
    """The closing price for a ticker on (or just before) a past date. Used to
    reconstruct a benchmark's level at decision time for the 'vs market' read.
    Cached long — a historical close doesn't change."""
    normalized = _normalize_ticker(ticker)
    cache_key = f"hist_price_{normalized}_{when.date().isoformat()}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        price = await asyncio.to_thread(_yfinance_close_on_sync, normalized, when)
    except Exception:
        logger.warning("historical price fetch failed for %s @ %s", normalized, when.date(), exc_info=True)
        return None
    if price and price > 0:
        _cache.set(cache_key, price, _CACHE_TTL_LONG)
    return price


async def fetch_live_price(ticker: str) -> float | None:
    """Return the latest market price for a ticker, cached for 60 seconds.

    Normalises the T212 ticker format first.  Returns None if yfinance cannot
    find the symbol — callers should fall back to the stored DB price.
    """
    normalized = _normalize_ticker(ticker)
    cache_key = f"live_price_{normalized}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        price = await asyncio.to_thread(_yfinance_fast_price_sync, normalized)
    except Exception:
        logger.warning("live price fetch failed for %s", normalized, exc_info=True)
        return None

    if price and price > 0:
        _cache.set(cache_key, price, _CACHE_TTL_PRICE)
    return price


def _yfinance_fx_sync(pair: str) -> float | None:
    """Blocking call — fetch FX rate via yfinance, e.g. USDGBP=X."""
    import yfinance as yf

    t = yf.Ticker(pair)
    info = dict(t.info)
    price = info.get("regularMarketPrice") or info.get("price") or info.get("previousClose")
    return float(price) if price else None


async def _fetch_fx_rate_direct(from_ccy: str, to_ccy: str) -> float | None:
    pair = f"{from_ccy}{to_ccy}=X"
    try:
        return await asyncio.to_thread(_yfinance_fx_sync, pair)
    except Exception:
        logger.warning("yfinance FX lookup failed for %s", pair, exc_info=True)
        return None


async def get_fx_rate(from_ccy: str, to_ccy: str) -> float:
    """Return the exchange rate from_ccy → to_ccy, cached for 4 hours.

    Falls back to 1.0 (no conversion) if the rate cannot be fetched, with a
    warning logged so the issue is visible without crashing the sync.
    """
    if from_ccy == to_ccy:
        return 1.0
    cache_key = f"fx_{from_ccy}_{to_ccy}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    rate = await _fetch_fx_rate_direct(from_ccy, to_ccy)
    if rate is None or rate <= 0:
        # Try inverse and reciprocate
        inverse = await _fetch_fx_rate_direct(to_ccy, from_ccy)
        if inverse and inverse > 0:
            rate = 1.0 / inverse

    if rate is None or rate <= 0:
        logger.warning("FX rate unavailable for %s→%s, using 1.0 fallback", from_ccy, to_ccy)
        rate = 1.0

    _cache.set(cache_key, rate, _CACHE_TTL_SHORT)
    return rate


QUALITATIVE_KEYWORDS = (
    "earnings",
    "guidance",
    "downgrade",
    "dividend",
    "management",
    "regulation",
    "litigation",
    "ceo",
    "founder",
    "executive",
    "resign",
    "appoint",
    "cfo",
    "coo",
)
QUALITATIVE_TOPICS = {
    "earnings",
    "finance",
    "economy_fiscal",
    "economy_monetary",
    "economy_macro",
}
TRANSCRIPT_KEYWORDS = (
    "guidance",
    "margin",
    "margins",
    "demand",
    "slowdown",
    "headwind",
    "pricing",
    "regulation",
    "litigation",
    "competition",
    "restructuring",
    "inventory",
    "pipeline",
    "backlog",
)
INSIDER_ROLE_KEYWORDS = (
    "founder",
    "ceo",
    "cfo",
    "coo",
    "chief",
    "director",
    "officer",
    "president",
    "chair",
    "board",
)
INSIDER_SALE_KEYWORDS = ("sale", "sell", "sold", "dispose", "disposition")
INSIDER_BUY_KEYWORDS = ("buy", "bought", "purchase", "acquire", "acquisition")
_NEWS_EVENT_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "product_ramp_update",
        (
            "deployment",
            "rollout",
            "ramp",
            "shipment",
            "shipments",
            "availability",
            "launch",
            "production",
            "supply constraint",
        ),
    ),
    (
        "contract_renewal_update",
        (
            "renewal",
            "renewals",
            "contract extension",
            "customer expansion",
            "signed demand",
            "bookings",
            "backlog",
            "remaining performance obligations",
            "rpo",
        ),
    ),
    (
        "funding_condition_update",
        (
            "funding capacity",
            "warehouse facility",
            "asset backed",
            "abs market",
            "securitization",
            "funding cost",
            "liquidity facility",
            "credit facility",
        ),
    ),
    (
        "customer_capex_signal",
        (
            "capital spending",
            "capex",
            "infrastructure spending",
            "data center spending",
            "budget expansion",
            "budget cuts",
            "customer demand",
        ),
    ),
    (
        "margin_pressure_update",
        (
            "margin pressure",
            "gross margin",
            "operating margin",
            "profitability",
            "pricing pressure",
            "cost drag",
            "overhead drag",
            "expense pressure",
        ),
    ),
)
_ROUNDUP_NOISE_PATTERNS: tuple[str, ...] = (
    "stocks to buy",
    "stocks to watch",
    "stock is up today",
    "stock is down today",
    "why amd stock is up today",
    "why amd stock is down today",
    "why intel, amd",
    "why nvidia, amd",
    "couldn't stop buzzing",
    "next nvidia",
    "top stocks",
    "best stocks",
    "market recap",
    "weekly roundup",
    "roundup",
    "wallstreetbets",
)
_GENERIC_NEWS_RELEVANCE_FLOOR = 0.35


@dataclass
class NewsItem:
    id: str
    headline: str
    summary: str
    published_at: datetime
    source: str
    url: str
    sentiment: float | None
    topics: list[str]
    ticker_relevance: float | None
    primary_ticker: str | None = None


@dataclass
class TranscriptSignal:
    quarter: str
    call_date: datetime | None
    sentiment: float | None
    sentiment_label: str | None
    highlights: list[str]
    excerpt: str
    full_text: str | None = None


def _classify_news_event_type(combined_text: str) -> tuple[str, list[str]]:
    def _matches_keyword(keyword: str) -> bool:
        escaped = re.escape(keyword.lower())
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        return re.search(pattern, combined_text) is not None

    for event_type, keywords in _NEWS_EVENT_PATTERNS:
        found = [keyword for keyword in keywords if _matches_keyword(keyword)]
        if found:
            return event_type, found[:4]
    return "news_or_earnings_candidate", []


def _looks_like_roundup_noise(headline: str, summary: str) -> bool:
    text = f"{headline} {summary}".lower()
    return any(pattern in text for pattern in _ROUNDUP_NOISE_PATTERNS)


MAX_CURRENT_TRANSCRIPT_AGE_DAYS = 120
MAX_RECENT_TRANSCRIPT_QUARTERS = 2


@dataclass
class InsiderTransaction:
    id: str
    filing_date: datetime | None
    transaction_date: datetime | None
    insider_name: str
    title: str
    transaction_type: str
    shares: float | None
    share_price: float | None
    value: float | None


@dataclass
class CompanyData:
    ticker: str
    name: str
    sector: str
    industry: str
    current_price: float | None
    market_cap: float | None
    pe_ratio: float | None
    revenue_growth_yoy: float | None
    earnings_growth_yoy: float | None
    dividend_yield: float | None
    description: str
    recent_news: list[str]
    upcoming_earnings_date: datetime | None
    recent_earnings_surprise_pct: float | None
    news_items: list[NewsItem]
    provider_payload: dict[str, Any] = field(default_factory=dict)
    recent_fiscal_quarter: str | None = None
    recent_fiscal_quarters: list[str] = field(default_factory=list)
    earnings_call: TranscriptSignal | None = None
    earnings_calls: list[TranscriptSignal] = field(default_factory=list)
    insider_transactions: list[InsiderTransaction] = field(default_factory=list)
    country: str = "Unknown"
    currency: str | None = None  # ISO 4217 as reported by the data provider (authoritative)


def is_current_earnings_call(
    earnings_call: TranscriptSignal | None,
    *,
    now: datetime | None = None,
    recent_fiscal_quarter: str | None = None,
) -> bool:
    """Whether a transcript is current enough to use as live evidence.

    If we have a call date, trust recency. If we do not, only keep the
    transcript when it matches the most recent reported fiscal quarter.
    """
    if earnings_call is None:
        return False

    reference_now = now or datetime.now(timezone.utc)
    if earnings_call.call_date is not None:
        return earnings_call.call_date >= (reference_now - timedelta(days=MAX_CURRENT_TRANSCRIPT_AGE_DAYS))

    if recent_fiscal_quarter and earnings_call.quarter:
        return earnings_call.quarter == recent_fiscal_quarter

    return False


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()
    iso_candidate = normalized.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_candidate)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    normalized = normalized.rstrip("Z")
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%dT%H%M",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _parse_alpha_vantage_quote(payload: dict[str, Any]) -> float | None:
    quote = payload.get("Global Quote", payload)
    return _to_float(quote.get("05. price") or quote.get("price"))


def _parse_alpha_vantage_overview(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": payload.get("Name") or payload.get("name") or "",
        "sector": payload.get("Sector") or "",
        "industry": payload.get("Industry") or "",
        "country": payload.get("Country") or "",
        "currency": payload.get("Currency") or "",
        "description": payload.get("Description") or "",
        "market_cap": _to_float(payload.get("MarketCapitalization")),
        "pe_ratio": _to_float(payload.get("PERatio")),
        "dividend_yield": _to_float(payload.get("DividendYield")),
        "revenue_growth_yoy": _to_float(payload.get("QuarterlyRevenueGrowthYOY")),
        "earnings_growth_yoy": _to_float(payload.get("QuarterlyEarningsGrowthYOY")),
    }


def _parse_alpha_vantage_earnings(payload: dict[str, Any]) -> dict[str, Any]:
    quarters = payload.get("quarterlyEarnings", [])
    recent_quarter = quarters[0] if quarters else {}

    surprise_pct = _to_float(recent_quarter.get("surprisePercentage"))
    report_date = _to_datetime(recent_quarter.get("reportedDate"))
    fiscal_date_ending = _to_datetime(recent_quarter.get("fiscalDateEnding"))

    return {
        "recent_earnings_surprise_pct": surprise_pct,
        "recent_reported_at": report_date,
        "recent_fiscal_quarter": _quarter_string(fiscal_date_ending or report_date),
        "recent_fiscal_quarters": [
            quarter
            for quarter in (
                _quarter_string(
                    _to_datetime(row.get("fiscalDateEnding")) or _to_datetime(row.get("reportedDate"))
                )
                for row in quarters[:MAX_RECENT_TRANSCRIPT_QUARTERS]
                if isinstance(row, dict)
            )
            if quarter
        ],
    }


def _parse_alpha_vantage_earnings_calendar(csv_payload: str, ticker: str) -> datetime | None:
    lines = [line.strip() for line in csv_payload.splitlines() if line.strip()]
    if not lines:
        return None

    header = [column.strip() for column in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        values = [column.strip() for column in line.split(",")]
        if len(values) != len(header):
            continue
        rows.append(dict(zip(header, values)))

    for row in rows:
        symbol = row.get("symbol") or row.get("ticker")
        if symbol == ticker:
            return _to_datetime(row.get("reportDate"))
    return None


def _article_id(article: dict[str, Any]) -> str:
    url = article.get("url", "")
    published = article.get("time_published", "")
    title = article.get("title", "")
    seed = f"{url}|{published}|{title}".encode("utf-8")
    return sha256(seed).hexdigest()[:24]


def _transaction_id(transaction: dict[str, Any]) -> str:
    seed = "|".join(
        str(
            transaction.get(key, "")
        )
        for key in (
            "insider_name",
            "insiderName",
            "name",
            "transaction_date",
            "transactionDate",
            "transaction_type",
            "transactionType",
            "shares",
            "share_price",
        )
    ).encode("utf-8")
    return sha256(seed).hexdigest()[:24]


def _quarter_string(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    quarter = ((dt.month - 1) // 3) + 1
    return f"{dt.year}Q{quarter}"


def _fallback_transcript_quarters(
    *,
    reference_now: datetime | None = None,
    count: int = 2,
) -> list[str]:
    """Best-effort calendar-quarter fallback when providers expose no recent
    earnings metadata. Starts from the most recently completed calendar
    quarter — asking a transcript provider for the quarter we're currently
    inside guarantees a 400 or empty response, since no company can report
    on a quarter that hasn't ended."""
    if count <= 0:
        return []
    current = reference_now or datetime.now(timezone.utc)
    year = current.year
    quarter = ((current.month - 1) // 3)
    if quarter == 0:
        year -= 1
        quarter = 4
    quarters: list[str] = []
    for _ in range(count):
        quarters.append(f"{year}Q{quarter}")
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return quarters


def _extract_text_segments(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        segments: list[str] = []
        for item in value:
            if isinstance(item, str):
                segments.append(item)
            elif isinstance(item, dict):
                for key in ("content", "text", "remarks", "answer", "question", "transcript"):
                    text = item.get(key)
                    if isinstance(text, str) and text.strip():
                        segments.append(text.strip())
                        break
        return segments
    if isinstance(value, dict):
        return [str(v).strip() for v in value.values() if isinstance(v, str) and v.strip()]
    return []


def _extract_transcript_highlights(transcript_text: str, *, limit: int = 3) -> list[str]:
    if not transcript_text.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", transcript_text.strip())
    highlights: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = sentence.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if not any(keyword in lowered for keyword in TRANSCRIPT_KEYWORDS):
            continue
        compact = normalized[:280]
        if compact in seen:
            continue
        seen.add(compact)
        highlights.append(compact)
        if len(highlights) >= limit:
            break
    return highlights


def _extract_ticker_relevance(article: dict[str, Any], ticker: str) -> float | None:
    sentiment = article.get("ticker_sentiment", [])
    if not isinstance(sentiment, list):
        return None
    for item in sentiment:
        if item.get("ticker") == ticker:
            return _to_float(item.get("relevance_score"))
    return None


def _extract_primary_ticker(article: dict[str, Any]) -> str | None:
    sentiment = article.get("ticker_sentiment", [])
    if not isinstance(sentiment, list):
        return None

    best_ticker: str | None = None
    best_score = float("-inf")
    for item in sentiment:
        raw_ticker = str(item.get("ticker") or "").strip().upper()
        score = _to_float(item.get("relevance_score"))
        if not raw_ticker or score is None:
            continue
        if score > best_score:
            best_ticker = raw_ticker
            best_score = score
    return best_ticker


def _parse_alpha_vantage_news_item(article: dict[str, Any], ticker: str) -> NewsItem | None:
    published_at = _to_datetime(article.get("time_published"))
    if published_at is None:
        return None

    topics = [topic.get("topic") for topic in article.get("topics", []) if topic.get("topic")]
    overall_sentiment = _to_float(article.get("overall_sentiment_score"))

    return NewsItem(
        id=_article_id(article),
        headline=article.get("title", ""),
        summary=article.get("summary", ""),
        published_at=published_at,
        source=article.get("source", ""),
        url=article.get("url", ""),
        sentiment=overall_sentiment,
        topics=topics,
        ticker_relevance=_extract_ticker_relevance(article, ticker),
        primary_ticker=_extract_primary_ticker(article),
    )


def _parse_alpha_vantage_news(payload: dict[str, Any], ticker: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    for article in payload.get("feed", []):
        item = _parse_alpha_vantage_news_item(article, ticker)
        if item is not None:
            items.append(item)
    return items


def _parse_alpha_vantage_transcript(payload: dict[str, Any]) -> TranscriptSignal | None:
    if not payload:
        return None

    transcript_text = " ".join(
        segment for segment in _extract_text_segments(payload.get("transcript") or payload.get("content")) if segment
    ).strip()
    sentiment = _to_float(
        payload.get("overall_sentiment_score")
        or payload.get("sentiment_score")
        or payload.get("sentiment")
    )
    sentiment_label = (
        payload.get("overall_sentiment_label")
        or payload.get("sentiment_label")
        or payload.get("sentimentLabel")
    )
    call_date = _to_datetime(
        payload.get("date")
        or payload.get("call_date")
        or payload.get("reportedDate")
        or payload.get("time_published")
    )
    quarter = payload.get("quarter") or payload.get("fiscalQuarter") or ""

    if not transcript_text and sentiment is None and call_date is None and not quarter:
        return None

    highlights = _extract_transcript_highlights(transcript_text)
    excerpt = " ".join(highlights[:2]) if highlights else transcript_text[:400]

    return TranscriptSignal(
        quarter=quarter,
        call_date=call_date,
        sentiment=sentiment,
        sentiment_label=sentiment_label,
        highlights=highlights,
        excerpt=excerpt,
        full_text=transcript_text[:30_000] if transcript_text else None,
    )


def _transcript_payload_error(payload: dict[str, Any]) -> str | None:
    for key in ("Error Message", "error", "message", "Note", "Information", "information"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
    return None


def _current_earnings_calls(
    transcripts: list[TranscriptSignal],
    *,
    now: datetime | None = None,
    recent_fiscal_quarters: list[str] | None = None,
    recent_fiscal_quarter: str | None = None,
) -> list[TranscriptSignal]:
    reference_now = now or datetime.now(timezone.utc)
    recent_quarters = [quarter for quarter in (recent_fiscal_quarters or []) if quarter]
    if recent_fiscal_quarter and recent_fiscal_quarter not in recent_quarters:
        recent_quarters.append(recent_fiscal_quarter)

    current = [
        transcript
        for transcript in transcripts
        if is_current_earnings_call(
            transcript,
            now=reference_now,
            recent_fiscal_quarter=recent_fiscal_quarter,
        )
    ]
    if recent_quarters:
        quarter_rank = {quarter: index for index, quarter in enumerate(recent_quarters)}
        current.sort(
            key=lambda transcript: (
                quarter_rank.get(transcript.quarter, 99),
                -(transcript.call_date or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
            ),
        )
    else:
        current.sort(key=lambda transcript: transcript.call_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return current


def _parse_alpha_vantage_insider_transactions(payload: dict[str, Any]) -> list[InsiderTransaction]:
    raw_items = (
        payload.get("transactions")
        or payload.get("insiderTransactions")
        or payload.get("data")
        or []
    )
    items: list[InsiderTransaction] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        filing_date = _to_datetime(raw.get("filing_date") or raw.get("filingDate"))
        transaction_date = _to_datetime(raw.get("transaction_date") or raw.get("transactionDate"))
        insider_name = raw.get("insider_name") or raw.get("insiderName") or raw.get("name") or ""
        title = raw.get("title") or raw.get("officerTitle") or raw.get("insiderTitle") or raw.get("position") or ""
        transaction_type = (
            raw.get("transaction_type")
            or raw.get("transactionType")
            or raw.get("acquisition_or_disposition")
            or raw.get("acquisitionOrDisposition")
            or raw.get("type")
            or ""
        )
        shares = _to_float(raw.get("shares") or raw.get("shareCount") or raw.get("transactionShares"))
        share_price = _to_float(raw.get("share_price") or raw.get("sharePrice") or raw.get("price"))
        value = _to_float(raw.get("value"))
        if value is None and shares is not None and share_price is not None:
            value = shares * share_price
        items.append(
            InsiderTransaction(
                id=_transaction_id(raw),
                filing_date=filing_date,
                transaction_date=transaction_date,
                insider_name=insider_name,
                title=title,
                transaction_type=str(transaction_type),
                shares=shares,
                share_price=share_price,
                value=value,
            )
        )

    items.sort(
        key=lambda item: item.transaction_date or item.filing_date or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items


def _candidate_sort_key(candidate: dict[str, Any]) -> float:
    evidence = candidate.get("evidence", {})
    timestamp = (
        evidence.get("published_at")
        or evidence.get("transaction_date")
        or evidence.get("call_date")
        or evidence.get("filing_date")
    )
    if not isinstance(timestamp, str):
        return float("-inf")
    parsed = _to_datetime(timestamp)
    if parsed is None:
        return float("-inf")
    return parsed.timestamp()


def _build_earnings_surprise_candidate(recent_earnings_surprise_pct: float | None) -> dict[str, Any] | None:
    if recent_earnings_surprise_pct is None or abs(recent_earnings_surprise_pct) < 5:
        return None
    # "surprise was 5.6%" is ambiguous downstream — a beat reads identical to a
    # miss. Spell out the direction so both the LLM classifier and a human
    # reading the conviction log know which way the news cuts.
    direction = "beat" if recent_earnings_surprise_pct > 0 else "missed"
    magnitude = abs(recent_earnings_surprise_pct)
    return {
        "event_type": "earnings_surprise",
        "description": f"Recent earnings {direction} expectations by {magnitude:.1f}%.",
        "evidence": {"recent_earnings_surprise_pct": recent_earnings_surprise_pct},
    }


def _build_upcoming_earnings_candidate(
    upcoming_earnings_date: datetime | None,
    *,
    now: datetime,
) -> dict[str, Any] | None:
    if upcoming_earnings_date is None:
        return None
    days_until_earnings = (upcoming_earnings_date.date() - now.date()).days
    if not 0 <= days_until_earnings <= 7:
        return None
    return {
        "event_type": "upcoming_earnings",
        "description": f"Earnings are scheduled for {upcoming_earnings_date.date().isoformat()}.",
        "evidence": {"upcoming_earnings_date": upcoming_earnings_date.isoformat()},
    }


def _build_transcript_candidate(
    earnings_call: TranscriptSignal | None,
    *,
    now: datetime,
    transcript_max_age_days: int = 14,
) -> tuple[int, dict[str, Any]] | None:
    if earnings_call is None:
        return None

    transcript_cutoff = now - timedelta(days=transcript_max_age_days)
    negative_sentiment = earnings_call.sentiment is not None and earnings_call.sentiment <= -0.15
    if (
        earnings_call.call_date is None
        or earnings_call.call_date < transcript_cutoff
        or (not earnings_call.highlights and not negative_sentiment)
    ):
        return None

    transcript_summary = earnings_call.highlights[0] if earnings_call.highlights else earnings_call.excerpt
    sentiment_suffix = ""
    if negative_sentiment and earnings_call.sentiment_label:
        sentiment_suffix = f" Transcript sentiment is {earnings_call.sentiment_label.lower()}."
    return (
        0,
        {
            "event_type": "earnings_call_transcript",
            "description": (
                f"{earnings_call.quarter or 'Latest'} earnings call signaled: "
                f"{transcript_summary}{sentiment_suffix}"
            ).strip(),
            "evidence": {
                "quarter": earnings_call.quarter,
                "call_date": earnings_call.call_date.isoformat() if earnings_call.call_date else None,
                "sentiment": earnings_call.sentiment,
                "sentiment_label": earnings_call.sentiment_label,
                "highlights": earnings_call.highlights,
                "excerpt": earnings_call.excerpt,
                "transcript_id": f"transcript:{earnings_call.quarter or 'latest'}",
                "full_transcript": earnings_call.full_text,
            },
        },
    )


def _build_insider_candidate(
    transaction: InsiderTransaction,
    *,
    now: datetime,
) -> tuple[int, dict[str, Any]] | None:
    txn_date = transaction.transaction_date or transaction.filing_date
    if txn_date is None or txn_date < (now - timedelta(days=30)):
        return None

    role_text = f"{transaction.title} {transaction.insider_name}".lower()
    if not any(keyword in role_text for keyword in INSIDER_ROLE_KEYWORDS):
        return None

    txn_type = transaction.transaction_type.lower()
    direction = None
    priority = 2
    if any(keyword in txn_type for keyword in INSIDER_SALE_KEYWORDS):
        direction = "sale"
        priority = 1
    elif any(keyword in txn_type for keyword in INSIDER_BUY_KEYWORDS):
        direction = "purchase"
        priority = 2
    if direction is None:
        return None

    shares_text = f"{transaction.shares:,.0f} shares" if transaction.shares is not None else "shares"
    return (
        priority,
        {
            "event_type": "insider_transaction",
            "description": (
                f"{transaction.insider_name or 'An insider'}"
                f"{f' ({transaction.title})' if transaction.title else ''} reported a recent {direction} of "
                f"{shares_text}."
            ),
            "evidence": {
                "transaction_id": transaction.id,
                "transaction_date": txn_date.isoformat(),
                "filing_date": transaction.filing_date.isoformat() if transaction.filing_date else None,
                "insider_name": transaction.insider_name,
                "title": transaction.title,
                "transaction_type": transaction.transaction_type,
                "shares": transaction.shares,
                "share_price": transaction.share_price,
                "value": transaction.value,
            },
        },
    )


def _build_news_candidate(
    item: NewsItem,
    *,
    now: datetime,
    ticker: str | None = None,
) -> tuple[int, dict[str, Any]] | None:
    if item.published_at < (now - timedelta(days=7)):
        return None

    combined_text = f"{item.headline} {item.summary}".lower()
    topic_match = any(topic in QUALITATIVE_TOPICS for topic in item.topics)
    keyword_match = any(keyword in combined_text for keyword in QUALITATIVE_KEYWORDS)
    if not (topic_match or keyword_match):
        return None

    ticker_text_mentioned = bool(ticker and ticker.lower() in combined_text)
    if (
        ticker
        and item.primary_ticker
        and item.primary_ticker != ticker.upper()
        and not ticker_text_mentioned
    ):
        return None

    if item.ticker_relevance is not None:
        # Alpha Vantage provides a relevance score — use it
        if item.ticker_relevance < 0.1:
            return None
    else:
        # yfinance news has no relevance score; require the ticker to appear in the text
        if ticker and not ticker_text_mentioned:
            return None

    if _looks_like_roundup_noise(item.headline, item.summary):
        return None

    event_type, matched_topics = _classify_news_event_type(combined_text)
    if (
        event_type == "news_or_earnings_candidate"
        and item.ticker_relevance is not None
        and item.ticker_relevance < _GENERIC_NEWS_RELEVANCE_FLOOR
    ):
        return None
    topic_context = ", ".join(matched_topics)

    return (
        3,
        {
            "event_type": event_type,
            "description": f"{item.headline}: {item.summary}" if item.summary else item.headline,
            "evidence": {
                "article_id": item.id,
                "headline": item.headline,
                "summary": item.summary,
                "published_at": item.published_at.isoformat(),
                "source": item.source,
                "url": item.url,
                "sentiment": item.sentiment,
                "topics": item.topics,
                "ticker_relevance": item.ticker_relevance,
                "matched_topics": matched_topics,
                "topic_context": topic_context,
            },
        },
    )


def _fetch_analyst_consensus_sync(
    ticker: str,
    previous_target: float | None,
) -> dict | None:
    """Blocking: fetch analyst ratings + price targets via yfinance."""
    import yfinance as yf

    try:
        t = yf.Ticker(ticker)
        recs = getattr(t, "recommendations", None)
        targets = getattr(t, "analyst_price_targets", None) or {}

        mean_target = targets.get("mean")
        current_price_raw = getattr(t.fast_info, "last_price", None)
        current_price = float(current_price_raw) if current_price_raw else None

        def _col_sum(df: Any, col: str) -> int:
            return int(df[col].sum()) if col in df.columns else 0

        net_changes = 0
        if recs is not None and not recs.empty:
            # yfinance recommendations DataFrame: period column "0m"=current, "-1m"=last month
            recent = recs[recs["period"].isin(["0m", "-1m"])] if "period" in recs.columns else recs.head(2)
            if not recent.empty:
                upgrades = _col_sum(recent, "strongBuy") + _col_sum(recent, "buy")
                downgrades = _col_sum(recent, "sell") + _col_sum(recent, "strongSell")
                net_changes = upgrades - downgrades

        if mean_target is None and net_changes == 0:
            return None

        return {
            "net_changes_30d": net_changes,
            "mean_target": float(mean_target) if mean_target is not None else None,
            "current_price": current_price,
            "previous_target": previous_target,
        }
    except Exception:
        return None


def _build_analyst_revision_candidate(
    consensus: dict,
    ticker: str | None = None,
) -> tuple[int, dict[str, Any]] | None:
    """Return (priority, candidate) if firing conditions are met, else None.

    Fires when: net rating changes >= 2 OR price target moved >10% vs previous run.
    Never thesis_breaking — analyst consensus alone does not break a thesis.
    """
    net = consensus.get("net_changes_30d", 0)
    mean_target = consensus.get("mean_target")
    previous_target = consensus.get("previous_target")
    current_price = consensus.get("current_price")

    target_moved_significantly = (
        mean_target is not None
        and previous_target is not None
        and previous_target > 0
        and abs(mean_target - previous_target) / previous_target > 0.10
    )
    target_below_price = (
        mean_target is not None
        and current_price is not None
        and mean_target < current_price
    )

    fires = abs(net) >= 2 or target_moved_significantly
    if not fires:
        return None

    if net < 0:
        direction = f"{abs(net)} net analyst downgrade(s) in the past 30 days"
    elif net > 0:
        direction = f"{net} net analyst upgrade(s) in the past 30 days"
    else:
        direction = "significant analyst price target revision"

    target_note = ""
    if mean_target is not None and current_price is not None:
        pct = ((mean_target - current_price) / current_price) * 100
        target_note = f" Consensus target ${mean_target:.0f} ({pct:+.0f}% vs current)."

    evidence: dict[str, Any] = {
        "net_changes_30d": net,
        "mean_target": mean_target,
        "current_price": current_price,
        "previous_target": previous_target,
        "target_below_price": target_below_price,
        "analyst_revision_id": ticker,
    }

    priority = 2 if net < 0 or target_below_price else 1

    return priority, {
        "event_type": "analyst_revision",
        "description": f"{direction}.{target_note}",
        "evidence": evidence,
    }


def shortlist_qualitative_candidates(
    news_items: list[NewsItem],
    recent_earnings_surprise_pct: float | None,
    upcoming_earnings_date: datetime | None,
    earnings_call: TranscriptSignal | None = None,
    earnings_calls: list[TranscriptSignal] | None = None,
    insider_transactions: list[InsiderTransaction] | None = None,
    *,
    now: datetime | None = None,
    max_candidates: int = 8,
    ticker: str | None = None,
    previous_analyst_target: float | None = None,
    transcript_max_age_days: int = 14,
) -> list[dict[str, Any]]:
    reference_now = now or datetime.now(timezone.utc)
    candidates: list[dict[str, Any]] = []
    qualitative_candidates: list[tuple[int, dict[str, Any]]] = []
    seen_ids: set[str] = set()

    # Analyst consensus (yfinance, free, no new API keys)
    if ticker:
        consensus = _fetch_analyst_consensus_sync(ticker, previous_analyst_target)
        if consensus is not None:
            analyst_candidate = _build_analyst_revision_candidate(consensus, ticker=ticker)
            if analyst_candidate is not None:
                qualitative_candidates.append(analyst_candidate)

    earnings_surprise_candidate = _build_earnings_surprise_candidate(recent_earnings_surprise_pct)
    if earnings_surprise_candidate is not None:
        candidates.append(earnings_surprise_candidate)

    upcoming_earnings_candidate = _build_upcoming_earnings_candidate(upcoming_earnings_date, now=reference_now)
    if upcoming_earnings_candidate is not None:
        candidates.append(upcoming_earnings_candidate)

    transcript_pool = list(earnings_calls or [])
    if earnings_call is not None and not any(
        transcript.quarter == earnings_call.quarter and transcript.call_date == earnings_call.call_date
        for transcript in transcript_pool
    ):
        transcript_pool.append(earnings_call)

    seen_transcript_ids: set[str] = set()
    for transcript in transcript_pool:
        transcript_candidate = _build_transcript_candidate(
            transcript,
            now=reference_now,
            transcript_max_age_days=transcript_max_age_days,
        )
        if transcript_candidate is None:
            continue
        transcript_id = str(transcript_candidate[1].get("evidence", {}).get("transcript_id") or "")
        if transcript_id and transcript_id in seen_transcript_ids:
            continue
        if transcript_id:
            seen_transcript_ids.add(transcript_id)
        qualitative_candidates.append(transcript_candidate)

    for transaction in insider_transactions or []:
        insider_candidate = _build_insider_candidate(transaction, now=reference_now)
        if insider_candidate is not None:
            qualitative_candidates.append(insider_candidate)

    for item in news_items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        news_candidate = _build_news_candidate(item, now=reference_now, ticker=ticker)
        if news_candidate is not None:
            qualitative_candidates.append(news_candidate)

    qualitative_candidates.sort(
        key=lambda item: (
            item[0],
            -_candidate_sort_key(item[1]),
        ),
    )
    candidates.extend(candidate for _, candidate in qualitative_candidates[:max_candidates])

    return candidates


async def _alpha_vantage_request(client: httpx.AsyncClient, function: str, **params: Any) -> dict[str, Any] | str:
    response = await client.get(
        ALPHA_VANTAGE_BASE_URL,
        params={"function": function, "apikey": settings.alpha_vantage_api_key, **params},
        timeout=30.0,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "text/csv" in content_type or function == "EARNINGS_CALENDAR":
        return response.text
    data = response.json()
    if isinstance(data, dict):
        # Both "Note" (hard limit) and "Information" (soft rate-limit / premium-only) mean the
        # response is empty. Don't treat these as valid data.
        limit_msg = data.get("Note") or data.get("Information")
        if limit_msg:
            raise RuntimeError(limit_msg)
    return data


async def _cached_request(
    client: httpx.AsyncClient, function: str, ttl: float, **params: Any
) -> dict[str, Any] | str:
    cache_key = f"{function}:{':'.join(f'{k}={v}' for k, v in sorted(params.items()))}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    result = await _alpha_vantage_request(client, function, **params)
    _cache.set(cache_key, result, ttl)
    return result


async def _safe_cached_request(
    client: httpx.AsyncClient,
    function: str,
    ttl: float,
    fallback: dict[str, Any] | str,
    **params: Any,
) -> dict[str, Any] | str:
    try:
        return await _cached_request(client, function, ttl, **params)
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# yfinance provider
# ---------------------------------------------------------------------------

def _yfinance_info_sync(ticker: str) -> dict[str, Any]:
    """Blocking call — run via asyncio.to_thread."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    return dict(t.info)


def _yfinance_news_sync(ticker: str) -> list[dict[str, Any]]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    return list(t.news or [])


def _yfinance_earnings_dates_sync(ticker: str) -> list[dict[str, Any]]:
    import yfinance as yf

    t = yf.Ticker(ticker)
    try:
        df = t.earnings_dates
        if df is None or df.empty:
            return []
        rows = []
        for dt_index, row in df.iterrows():
            rows.append({
                "date": dt_index.to_pydatetime(),
                "eps_estimate": row.get("EPS Estimate"),
                "reported_eps": row.get("Reported EPS"),
                "surprise_pct": row.get("Surprise(%)"),
            })
        return rows
    except Exception:
        return []


async def _fetch_yfinance_overview(ticker: str) -> dict[str, str] | None:
    try:
        info = await asyncio.to_thread(_yfinance_info_sync, ticker)
    except Exception:
        logger.warning("yfinance overview failed for %s", ticker, exc_info=True)
        return None

    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector") or "Unknown"
    country = info.get("country") or "Unknown"
    currency = _normalize_currency(info.get("currency")) or ""
    return {"name": name, "sector": sector, "country": country, "currency": currency}


def _parse_yfinance_news(raw_news: list[dict[str, Any]], ticker: str) -> list[NewsItem]:
    items: list[NewsItem] = []
    for entry in raw_news:
        content = entry.get("content", entry)
        title = content.get("title") or ""
        summary_text = content.get("summary") or content.get("description") or ""
        pub_date = _to_datetime(content.get("pubDate") or content.get("displayTime"))
        if pub_date is None:
            continue
        provider = content.get("provider", {})
        source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
        canonical = content.get("canonicalUrl", {})
        url = canonical.get("url", "") if isinstance(canonical, dict) else ""
        article_id = content.get("id") or _article_id({"url": url, "time_published": pub_date.isoformat(), "title": title})

        items.append(NewsItem(
            id=str(article_id),
            headline=title,
            summary=summary_text,
            published_at=pub_date,
            source=source,
            url=url,
            sentiment=None,
            topics=[],
            ticker_relevance=None,
        ))
    return items


async def _fetch_yfinance_company_data(ticker: str, _retried: bool = False) -> CompanyData | None:
    try:
        info, raw_news, earnings_rows = await asyncio.gather(
            asyncio.to_thread(_yfinance_info_sync, ticker),
            asyncio.to_thread(_yfinance_news_sync, ticker),
            asyncio.to_thread(_yfinance_earnings_dates_sync, ticker),
        )
    except Exception:
        logger.warning("yfinance fetch failed for %s", ticker, exc_info=True)
        return None

    # yfinance returns an empty dict for unknown symbols. T212 non-US tickers
    # often have a single trailing disambiguation letter (e.g. ASMLA → ASML).
    # Retry once with the last character stripped before giving up.
    if not info and not _retried and len(ticker) > 2:
        fallback = ticker[:-1]
        logger.info("yfinance returned no data for %s, retrying as %s", ticker, fallback)
        return await _fetch_yfinance_company_data(fallback, _retried=True)

    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector") or "Unknown"
    industry = info.get("industry") or "Unknown"
    country = info.get("country") or "Unknown"
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")
    pe_ratio = info.get("trailingPE")
    dividend_yield = info.get("dividendYield")
    revenue_growth_yoy = info.get("revenueGrowth")
    earnings_growth_yoy = info.get("earningsGrowth")
    description = info.get("longBusinessSummary") or ""

    news_items = _parse_yfinance_news(raw_news, ticker)

    # Upcoming earnings date: first future date from earnings_dates
    now = datetime.now(timezone.utc)
    upcoming_earnings_date: datetime | None = None
    recent_earnings_surprise_pct: float | None = None
    recent_fiscal_quarter: str | None = None

    for row in earnings_rows:
        row_date = row["date"]
        if not hasattr(row_date, "tzinfo") or row_date.tzinfo is None:
            row_date = row_date.replace(tzinfo=timezone.utc)
        if row_date > now and upcoming_earnings_date is None:
            upcoming_earnings_date = row_date
        if row_date <= now and recent_earnings_surprise_pct is None:
            surprise = row.get("surprise_pct")
            if surprise is not None:
                recent_earnings_surprise_pct = float(surprise)
                recent_fiscal_quarter = _quarter_string(row_date)

    return CompanyData(
        ticker=ticker,
        name=name,
        sector=sector,
        industry=industry,
        country=country,
        current_price=_to_float(current_price),
        market_cap=_to_float(market_cap),
        pe_ratio=_to_float(pe_ratio),
        revenue_growth_yoy=_to_float(revenue_growth_yoy),
        earnings_growth_yoy=_to_float(earnings_growth_yoy),
        dividend_yield=_to_float(dividend_yield),
        description=description,
        recent_news=[item.headline for item in news_items],
        upcoming_earnings_date=upcoming_earnings_date,
        recent_earnings_surprise_pct=recent_earnings_surprise_pct,
        news_items=news_items,
        recent_fiscal_quarter=recent_fiscal_quarter,
        recent_fiscal_quarters=[recent_fiscal_quarter] if recent_fiscal_quarter else [],
        earnings_call=None,  # yfinance doesn't provide transcripts
        earnings_calls=[],
        insider_transactions=[],  # yfinance doesn't provide insider data
        provider_payload={"provider": "yfinance", "info": info},
        currency=_normalize_currency(info.get("currency")),
    )


async def fetch_company_overview(ticker: str) -> dict[str, str] | None:
    """Lightweight call returning {name, sector, country} or None."""
    ticker = _normalize_ticker(ticker)
    # Try yfinance first (no API key needed)
    result = await _fetch_yfinance_overview(ticker)
    if result is not None:
        return result

    # Fall back to Alpha Vantage if key is configured
    if not settings.alpha_vantage_api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            payload = await _cached_request(client, "OVERVIEW", _CACHE_TTL_LONG, symbol=ticker)
        if not isinstance(payload, dict):
            return None
        overview = _parse_alpha_vantage_overview(payload)
        return {
            "name": overview["name"] or ticker,
            "sector": overview["sector"] or "Unknown",
            "country": overview.get("country") or payload.get("Country") or "Unknown",
            "currency": _normalize_currency(overview.get("currency")) or "",
        }
    except Exception:
        return None


async def fetch_company_data(ticker: str) -> CompanyData | None:
    ticker = _normalize_ticker(ticker)
    if settings.market_data_provider == "yfinance":
        yfinance_data = await _fetch_yfinance_company_data(ticker)
        # yfinance itself has no transcripts; when a dedicated transcript key is
        # set (API Ninjas or Alpha Vantage), enrich here so the yfinance path is
        # a real transcript-capable option instead of always empty.
        if yfinance_data is None:
            return None
        if settings.api_ninjas_api_key or settings.alpha_vantage_api_key:
            yfinance_data = await _enrich_yfinance_with_transcripts(yfinance_data)
        return yfinance_data

    if settings.market_data_provider != "alpha_vantage":
        raise RuntimeError(f"Unsupported market data provider: {settings.market_data_provider}")

    if not settings.alpha_vantage_api_key:
        return await _fetch_yfinance_company_data(ticker)

    try:
        provider_payload = await _fetch_alpha_vantage_payloads(ticker)
        av_data = _build_company_data_from_alpha_vantage(ticker, provider_payload)
        av_has_basics = av_data.current_price is not None and av_data.sector != "Unknown"
        av_has_enrichment = bool(
            av_data.news_items or av_data.earnings_call or av_data.earnings_calls or av_data.insider_transactions
        )
        if av_has_basics:
            return av_data
        logger.info(
            "Alpha Vantage returned partial data for %s, merging with yfinance baseline",
            ticker,
        )
        yfinance_data = await _fetch_yfinance_company_data(ticker)
        if yfinance_data is None:
            return av_data if av_has_enrichment else None
        retry_quarters = list(yfinance_data.recent_fiscal_quarters or [])
        if not retry_quarters:
            retry_quarters = _fallback_transcript_quarters()
        if not av_data.earnings_calls and retry_quarters:
            transcript_result = await _fetch_transcript_payloads(
                ticker,
                retry_quarters,
            )
            transcript_payloads, transcript_diagnostics = _normalize_transcript_fetch_result(
                transcript_result,
                retry_quarters,
            )
            if not yfinance_data.recent_fiscal_quarters:
                transcript_diagnostics.setdefault("quarter_strategy", "calendar_fallback")
            if transcript_payloads:
                provider_payload["earnings_call_transcripts"] = transcript_payloads
                provider_payload["earnings_call_transcript"] = transcript_payloads[0]
            provider_payload["transcript_diagnostics"] = transcript_diagnostics
            av_data = _build_company_data_from_alpha_vantage(ticker, provider_payload)
        return _merge_company_data(yfinance_data, av_data)
    except Exception:
        logger.warning("Alpha Vantage fetch failed for %s, falling back to yfinance", ticker, exc_info=True)
        return await _fetch_yfinance_company_data(ticker)


async def _fetch_alpha_vantage_payloads(ticker: str) -> dict[str, Any]:
    provider_payload: dict[str, Any] = {}
    async with httpx.AsyncClient() as client:
        quote_payload = await _safe_cached_request(
            client,
            "GLOBAL_QUOTE",
            _CACHE_TTL_SHORT,
            {},
            symbol=ticker,
        )
        provider_payload["quote"] = quote_payload

        overview_payload = await _safe_cached_request(
            client,
            "OVERVIEW",
            _CACHE_TTL_LONG,
            {},
            symbol=ticker,
        )
        provider_payload["overview"] = overview_payload

        earnings_payload = await _safe_cached_request(
            client,
            "EARNINGS",
            _CACHE_TTL_LONG,
            {},
            symbol=ticker,
        )
        provider_payload["earnings"] = earnings_payload

        recent_quarters = _parse_alpha_vantage_earnings(
            earnings_payload if isinstance(earnings_payload, dict) else {}
        ).get("recent_fiscal_quarters") or []
        transcript_quarters = list(recent_quarters or _fallback_transcript_quarters())
        transcript_payloads, transcript_diagnostics = await _fetch_transcript_payloads(
            ticker,
            transcript_quarters,
            client=client,
        )
        if not recent_quarters:
            transcript_diagnostics.setdefault("quarter_strategy", "calendar_fallback")
        provider_payload["earnings_call_transcripts"] = transcript_payloads
        provider_payload["earnings_call_transcript"] = transcript_payloads[0] if transcript_payloads else {}
        provider_payload["transcript_diagnostics"] = transcript_diagnostics

        earnings_calendar_payload = await _safe_cached_request(
            client,
            "EARNINGS_CALENDAR",
            _CACHE_TTL_LONG,
            "",
            symbol=ticker,
            horizon="3month",
        )
        provider_payload["earnings_calendar"] = earnings_calendar_payload

        news_payload = await _safe_cached_request(
            client,
            "NEWS_SENTIMENT",
            _CACHE_TTL_SHORT,
            {"feed": []},
            tickers=ticker,
            sort="LATEST",
            limit=50,
        )
        provider_payload["news"] = news_payload

        insiders_payload = await _safe_cached_request(
            client,
            "INSIDER_TRANSACTIONS",
            _CACHE_TTL_SHORT,
            {"data": []},
            symbol=ticker,
            **{"from": (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()},
        )
        provider_payload["insider_transactions"] = insiders_payload

    return provider_payload


def _split_quarter_string(quarter: str) -> tuple[int, int] | None:
    """Return (year, q_num) for a 'YYYYQN' fiscal-quarter string, else None."""
    if not quarter or "Q" not in quarter:
        return None
    year_part, _, q_part = quarter.partition("Q")
    try:
        return int(year_part), int(q_part)
    except ValueError:
        return None


def _api_ninjas_to_transcript_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Reshape an API Ninjas response so the existing Alpha Vantage transcript
    parser can read it. The Developer tier returns the raw transcript text plus
    date/year/quarter; sentiment fields are absent, which the AV parser already
    treats as optional."""
    year = raw.get("year")
    q_num = raw.get("quarter")
    quarter = f"{year}Q{q_num}" if year and q_num else ""
    return {
        "transcript": raw.get("transcript") or "",
        "date": raw.get("date") or "",
        "quarter": quarter,
    }


async def _fetch_api_ninjas_transcript_payloads(
    ticker: str,
    quarters: list[str] | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch earnings-call transcripts from API Ninjas. Same return shape as the
    Alpha Vantage fetcher so the downstream pipeline is provider-agnostic."""
    recent_quarters = [quarter for quarter in (quarters or []) if quarter]
    diagnostics: dict[str, Any] = {
        "requested_quarters": recent_quarters[:MAX_RECENT_TRANSCRIPT_QUARTERS],
        "returned_quarters": [],
        "empty_quarters": [],
        "unusable_quarters": [],
        "error_quarters": {},
        "provider": "api_ninjas",
    }
    if not recent_quarters or not settings.api_ninjas_api_key:
        return [], diagnostics

    headers = {"X-Api-Key": settings.api_ninjas_api_key}

    async def _run(active_client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        transcript_payloads: list[dict[str, Any]] = []
        for quarter in diagnostics["requested_quarters"]:
            split = _split_quarter_string(quarter)
            if split is None:
                diagnostics["unusable_quarters"].append(quarter)
                continue
            year, q_num = split
            params = {"ticker": ticker, "year": year, "quarter": q_num}
            cache_key = f"api_ninjas:transcript:{ticker}:{year}:{q_num}"
            cached = _cache.get(cache_key)
            if cached is not None:
                raw = cached
            else:
                try:
                    response = await active_client.get(
                        API_NINJAS_TRANSCRIPT_URL,
                        headers=headers,
                        params=params,
                        timeout=15.0,
                    )
                except Exception as exc:
                    diagnostics["error_quarters"][quarter] = str(exc)[:200]
                    continue
                if response.status_code == 429:
                    diagnostics["error_quarters"][quarter] = "api_ninjas rate limit"
                    continue
                if response.status_code == 401 or response.status_code == 403:
                    diagnostics["error_quarters"][quarter] = f"api_ninjas auth ({response.status_code})"
                    # No point retrying other quarters if the key is bad.
                    return transcript_payloads, diagnostics
                if response.status_code >= 400:
                    diagnostics["error_quarters"][quarter] = f"api_ninjas http {response.status_code}"
                    continue
                try:
                    raw = response.json()
                except ValueError:
                    diagnostics["error_quarters"][quarter] = "api_ninjas invalid json"
                    continue
                # API Ninjas returns {} when the quarter isn't available.
                if not isinstance(raw, dict) or not raw.get("transcript"):
                    diagnostics["empty_quarters"].append(quarter)
                    continue
                _cache.set(cache_key, raw, _CACHE_TTL_LONG)
            payload = _api_ninjas_to_transcript_payload(raw)
            if _parse_alpha_vantage_transcript(payload) is None:
                diagnostics["unusable_quarters"].append(quarter)
                continue
            transcript_payloads.append(payload)
            diagnostics["returned_quarters"].append(quarter)
        return transcript_payloads, diagnostics

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as active_client:
        return await _run(active_client)


async def _enrich_yfinance_with_transcripts(company_data: "CompanyData") -> "CompanyData":
    """Attach transcript signals to a yfinance CompanyData in place. Uses the
    provider router so API Ninjas is preferred when configured, AV is fallback.
    Silent no-op if no transcript is found or both providers are unconfigured."""
    quarters = list(company_data.recent_fiscal_quarters or [])
    if not quarters:
        quarters = _fallback_transcript_quarters()
    if not quarters:
        return company_data

    payloads, diagnostics = await _fetch_transcript_payloads(company_data.ticker, quarters)
    if not company_data.recent_fiscal_quarters:
        diagnostics.setdefault("quarter_strategy", "calendar_fallback")
    provider_payload = dict(company_data.provider_payload or {})
    provider_payload["transcript_diagnostics"] = diagnostics
    if not payloads:
        company_data.provider_payload = provider_payload
        return company_data

    parsed = [
        signal
        for signal in (_parse_alpha_vantage_transcript(payload) for payload in payloads)
        if signal is not None
    ]
    current = _current_earnings_calls(
        parsed,
        recent_fiscal_quarters=company_data.recent_fiscal_quarters,
        recent_fiscal_quarter=company_data.recent_fiscal_quarter,
    )
    company_data.earnings_calls = current
    company_data.earnings_call = current[0] if current else None
    provider_payload["earnings_call_transcripts"] = payloads
    provider_payload["earnings_call_transcript"] = payloads[0]
    company_data.provider_payload = provider_payload
    return company_data


async def _fetch_transcript_payloads(
    ticker: str,
    quarters: list[str] | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch transcripts, preferring API Ninjas when configured, falling back
    to Alpha Vantage. AV stays available so an outage in either provider
    degrades gracefully instead of taking the pipeline down."""
    if settings.api_ninjas_api_key:
        payloads, diagnostics = await _fetch_api_ninjas_transcript_payloads(
            ticker, quarters, client=client
        )
        missing = [
            quarter for quarter in diagnostics.get("requested_quarters", [])
            if quarter not in set(diagnostics.get("returned_quarters", []))
        ]
        # If API Ninjas covered every requested quarter, we're done.
        if not missing:
            return payloads, diagnostics
        # Otherwise let AV fill the gaps when its key is set.
        if not settings.alpha_vantage_api_key:
            return payloads, diagnostics
        av_payloads, av_diagnostics = await _fetch_alpha_vantage_transcript_payloads(
            ticker, missing, client=client
        )
        combined = list(payloads) + list(av_payloads)
        returned = list(diagnostics.get("returned_quarters", [])) + list(av_diagnostics.get("returned_quarters", []))
        returned_set = set(returned)
        diagnostics["returned_quarters"] = returned
        # If AV covered a quarter API Ninjas failed on, drop the stale API
        # Ninjas error — it lies about the final outcome. Same for empty /
        # unusable buckets.
        diagnostics["error_quarters"] = {
            q: err for q, err in diagnostics.get("error_quarters", {}).items()
            if q not in returned_set
        }
        for key in ("empty_quarters", "unusable_quarters"):
            diagnostics[key] = [q for q in diagnostics.get(key, []) if q not in returned_set]
            for q in av_diagnostics.get(key, []):
                if q not in returned_set and q not in diagnostics[key]:
                    diagnostics[key].append(q)
        for q, err in av_diagnostics.get("error_quarters", {}).items():
            if q not in returned_set:
                diagnostics["error_quarters"][q] = err
        diagnostics["provider"] = "api_ninjas+alpha_vantage" if av_payloads else "api_ninjas"
        return combined, diagnostics
    return await _fetch_alpha_vantage_transcript_payloads(ticker, quarters, client=client)


async def _fetch_alpha_vantage_transcript_payloads(
    ticker: str,
    quarters: list[str] | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    recent_quarters = [quarter for quarter in (quarters or []) if quarter]
    diagnostics: dict[str, Any] = {
        "requested_quarters": recent_quarters[:MAX_RECENT_TRANSCRIPT_QUARTERS],
        "returned_quarters": [],
        "empty_quarters": [],
        "unusable_quarters": [],
        "error_quarters": {},
        "provider": "alpha_vantage",
    }
    if not recent_quarters or not settings.alpha_vantage_api_key:
        return [], diagnostics

    async def _run(active_client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        transcript_payloads: list[dict[str, Any]] = []
        for recent_quarter in diagnostics["requested_quarters"]:
            try:
                transcript_payload = await _cached_request(
                    active_client,
                    "EARNINGS_CALL_TRANSCRIPT",
                    _CACHE_TTL_LONG,
                    symbol=ticker,
                    quarter=recent_quarter,
                )
            except Exception as exc:
                diagnostics["error_quarters"][recent_quarter] = str(exc)[:200]
                continue
            if not isinstance(transcript_payload, dict) or not transcript_payload:
                diagnostics["empty_quarters"].append(recent_quarter)
                continue
            payload_error = _transcript_payload_error(transcript_payload)
            if payload_error:
                diagnostics["error_quarters"][recent_quarter] = payload_error
                continue
            if _parse_alpha_vantage_transcript(transcript_payload) is None:
                diagnostics["unusable_quarters"].append(recent_quarter)
                continue
            if isinstance(transcript_payload, dict) and transcript_payload:
                transcript_payloads.append(transcript_payload)
                diagnostics["returned_quarters"].append(recent_quarter)
        return transcript_payloads, diagnostics

    if client is not None:
        return await _run(client)
    async with httpx.AsyncClient() as active_client:
        return await _run(active_client)


def _normalize_transcript_fetch_result(
    result: Any,
    requested_quarters: list[str] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Accept both the newer `(payloads, diagnostics)` shape and the older
    payload-only shape still used by some test doubles / callers."""
    normalized_requested = [quarter for quarter in (requested_quarters or []) if quarter][
        :MAX_RECENT_TRANSCRIPT_QUARTERS
    ]
    default_diagnostics: dict[str, Any] = {
        "requested_quarters": normalized_requested,
        "returned_quarters": [],
        "empty_quarters": [],
        "unusable_quarters": [],
        "error_quarters": {},
    }

    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], list)
        and isinstance(result[1], dict)
    ):
        payloads = result[0]
        diagnostics = dict(default_diagnostics)
        diagnostics.update(result[1])
        return payloads, diagnostics

    payloads = result if isinstance(result, list) else []
    diagnostics = dict(default_diagnostics)
    diagnostics["returned_quarters"] = [
        str(payload.get("quarter"))
        for payload in payloads
        if isinstance(payload, dict) and payload.get("quarter")
    ]
    diagnostics["empty_quarters"] = [
        quarter for quarter in normalized_requested if quarter not in set(diagnostics["returned_quarters"])
    ]
    return payloads, diagnostics


def _merge_company_data(base: CompanyData, enrichment: CompanyData) -> CompanyData:
    """Preserve richer AV qualitative/transcript evidence on top of a yfinance baseline."""
    news_items = enrichment.news_items or base.news_items
    recent_news = enrichment.recent_news or base.recent_news
    provider_payload = dict(base.provider_payload or {})
    enrichment_payload = dict(enrichment.provider_payload or {})
    provider_payload.update({
        "baseline_provider": provider_payload.get("provider", "yfinance"),
        "enrichment_provider": enrichment_payload.get("provider", "alpha_vantage"),
        "alpha_vantage": enrichment_payload,
    })

    return CompanyData(
        ticker=base.ticker,
        name=base.name or enrichment.name,
        sector=base.sector if base.sector != "Unknown" else enrichment.sector,
        industry=base.industry if base.industry != "Unknown" else enrichment.industry,
        current_price=base.current_price if base.current_price is not None else enrichment.current_price,
        market_cap=base.market_cap if base.market_cap is not None else enrichment.market_cap,
        pe_ratio=base.pe_ratio if base.pe_ratio is not None else enrichment.pe_ratio,
        revenue_growth_yoy=base.revenue_growth_yoy if base.revenue_growth_yoy is not None else enrichment.revenue_growth_yoy,
        earnings_growth_yoy=base.earnings_growth_yoy if base.earnings_growth_yoy is not None else enrichment.earnings_growth_yoy,
        dividend_yield=base.dividend_yield if base.dividend_yield is not None else enrichment.dividend_yield,
        description=base.description or enrichment.description,
        recent_news=recent_news,
        upcoming_earnings_date=base.upcoming_earnings_date or enrichment.upcoming_earnings_date,
        recent_earnings_surprise_pct=(
            base.recent_earnings_surprise_pct
            if base.recent_earnings_surprise_pct is not None
            else enrichment.recent_earnings_surprise_pct
        ),
        news_items=news_items,
        provider_payload=provider_payload,
        recent_fiscal_quarter=enrichment.recent_fiscal_quarter or base.recent_fiscal_quarter,
        recent_fiscal_quarters=enrichment.recent_fiscal_quarters or base.recent_fiscal_quarters,
        earnings_call=enrichment.earnings_call or base.earnings_call,
        earnings_calls=enrichment.earnings_calls or base.earnings_calls,
        insider_transactions=enrichment.insider_transactions or base.insider_transactions,
        country=base.country if base.country != "Unknown" else enrichment.country,
        currency=base.currency or enrichment.currency,
    )


def transcript_fetch_diagnostics(company_data: CompanyData | None) -> dict[str, Any]:
    if company_data is None:
        return {}
    provider_payload = company_data.provider_payload or {}
    if not isinstance(provider_payload, dict):
        return {}

    diagnostics = provider_payload.get("transcript_diagnostics")
    if not diagnostics and isinstance(provider_payload.get("alpha_vantage"), dict):
        diagnostics = provider_payload["alpha_vantage"].get("transcript_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}

    result = dict(diagnostics)
    result["available_transcripts"] = len(company_data.earnings_calls or [])
    result["recent_fiscal_quarters"] = list(company_data.recent_fiscal_quarters or [])
    return result


def _build_company_data_from_alpha_vantage(ticker: str, provider_payload: dict[str, Any]) -> CompanyData:
    quote_payload = provider_payload.get("quote", {})
    overview_payload = provider_payload.get("overview", {})
    earnings_payload = provider_payload.get("earnings", {})
    earnings_calendar_payload = provider_payload.get("earnings_calendar", "")
    news_payload = provider_payload.get("news", {"feed": []})
    transcript_payloads = provider_payload.get("earnings_call_transcripts", [])
    if not transcript_payloads and isinstance(provider_payload.get("earnings_call_transcript"), dict):
        transcript_payloads = [provider_payload.get("earnings_call_transcript")]
    insiders_payload = provider_payload.get("insider_transactions", {"data": []})

    overview = _parse_alpha_vantage_overview(overview_payload if isinstance(overview_payload, dict) else {})
    earnings = _parse_alpha_vantage_earnings(earnings_payload if isinstance(earnings_payload, dict) else {})
    upcoming_earnings_date = _parse_alpha_vantage_earnings_calendar(
        earnings_calendar_payload if isinstance(earnings_calendar_payload, str) else "",
        ticker,
    )
    news_items = _parse_alpha_vantage_news(news_payload if isinstance(news_payload, dict) else {"feed": []}, ticker)
    transcripts = [
        transcript
        for transcript in (
            _parse_alpha_vantage_transcript(payload if isinstance(payload, dict) else {})
            for payload in (transcript_payloads if isinstance(transcript_payloads, list) else [])
        )
        if transcript is not None
    ]
    current_transcripts = _current_earnings_calls(
        transcripts,
        now=datetime.now(timezone.utc),
        recent_fiscal_quarters=earnings.get("recent_fiscal_quarters") or [],
        recent_fiscal_quarter=earnings["recent_fiscal_quarter"],
    )
    transcript = current_transcripts[0] if current_transcripts else None
    insider_transactions = _parse_alpha_vantage_insider_transactions(
        insiders_payload if isinstance(insiders_payload, dict) else {"data": []}
    )

    return CompanyData(
        ticker=ticker,
        name=overview["name"] or ticker,
        sector=overview["sector"] or "Unknown",
        industry=overview["industry"] or "Unknown",
        country=overview["country"] or "Unknown",
        current_price=_parse_alpha_vantage_quote(quote_payload if isinstance(quote_payload, dict) else {}),
        market_cap=overview["market_cap"],
        pe_ratio=overview["pe_ratio"],
        revenue_growth_yoy=overview["revenue_growth_yoy"],
        earnings_growth_yoy=overview["earnings_growth_yoy"],
        dividend_yield=overview["dividend_yield"],
        description=overview["description"],
        recent_news=[item.headline for item in news_items],
        upcoming_earnings_date=upcoming_earnings_date,
        recent_earnings_surprise_pct=earnings["recent_earnings_surprise_pct"],
        news_items=news_items,
        recent_fiscal_quarter=earnings["recent_fiscal_quarter"],
        recent_fiscal_quarters=earnings.get("recent_fiscal_quarters") or [],
        earnings_call=transcript,
        earnings_calls=current_transcripts,
        insider_transactions=insider_transactions,
        provider_payload=provider_payload,
        currency=_normalize_currency(overview["currency"]),
    )
