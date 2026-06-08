import base64
import re
from dataclasses import dataclass

import httpx

from app.config import settings

# T212 structured format: {SYMBOL}_{COUNTRY_CODE}_{TYPE}
# Maps T212 country code → yfinance exchange suffix (empty string = no suffix needed)
_T212_COUNTRY_TO_SUFFIX: dict[str, str] = {
    "US": "",
    "UK": ".L",
    "DE": ".DE",
    "FR": ".PA",
    "NL": ".AS",
    "BE": ".BR",
    "IT": ".MI",
    "ES": ".MC",
    "PT": ".LS",
    "SE": ".ST",
    "DK": ".CO",
    "NO": ".OL",
    "FI": ".HE",
    "AT": ".VI",
    "CH": ".SW",
    "IE": ".IR",
    "PL": ".WA",
    "CZ": ".PR",
    "HU": ".BD",
    "SG": ".SI",
    "HK": ".HK",
    "AU": ".AX",
    "CA": ".TO",
    "JP": ".T",
}

# T212 older format: exchange letter embedded at end of symbol, followed by _EQ / _ETF
# e.g. VUAGL_EQ → VUAG.L, ASMLA_EQ → ASML.AS
_EMBEDDED_EXCHANGE_CHAR: dict[str, str] = {
    "L": ".L",    # London Stock Exchange
    "A": ".AS",   # Euronext Amsterdam
    "D": ".DE",   # XETRA
    "P": ".PA",   # Euronext Paris
    "B": ".BR",   # Euronext Brussels
    "M": ".MC",   # Bolsa Madrid
}

_T212_STRUCTURED_RE = re.compile(r"^([A-Z0-9.]+)_([A-Z]{2,3})_(EQ|ETF)$")
_T212_EMBEDDED_RE = re.compile(r"^([A-Z0-9.]+?)([A-Z])_(EQ|ETF)$")


def normalise_t212_ticker(raw: str) -> str:
    """Convert a Trading 212 instrument ticker to a standard yfinance-compatible ticker.

    T212 uses two formats:
    1. Structured: AAPL_US_EQ → AAPL, BARC_UK_EQ → BARC.L
    2. Embedded-exchange: VUAGL_EQ → VUAG.L, ASMLA_EQ → ASML.AS

    Unknown patterns are returned uppercased as-is.
    """
    raw = raw.upper()

    # Format 1: structured country code
    m = _T212_STRUCTURED_RE.match(raw)
    if m:
        symbol, country, _ = m.groups()
        suffix = _T212_COUNTRY_TO_SUFFIX.get(country)
        if suffix is not None:
            return symbol + suffix
        # Unknown country — return symbol without suffix as best effort
        return symbol

    # Format 2: embedded exchange letter before _EQ/_ETF
    m = _T212_EMBEDDED_RE.match(raw)
    if m:
        base, exchange_char, _ = m.groups()
        suffix = _EMBEDDED_EXCHANGE_CHAR.get(exchange_char)
        if suffix is not None:
            return base + suffix

    # No recognised pattern — return as-is
    return raw


@dataclass
class Trading212Position:
    ticker: str
    quantity: float
    average_price: float
    current_price: float
    ppl: float
    fx_ppl: float


_LIVE_URL = "https://live.trading212.com/api/v0"
_DEMO_URL = "https://demo.trading212.com/api/v0"


def build_auth_header(api_key: str, api_secret: str | None) -> str:
    """Return the Authorization header value for Trading 212.

    New accounts receive both a key and secret — use HTTP Basic Auth.
    Legacy accounts with a single key use it as a raw token.
    """
    api_key = api_key.strip()
    if api_secret:
        token = base64.b64encode(f"{api_key}:{api_secret.strip()}".encode()).decode()
        return f"Basic {token}"
    return api_key


class Trading212Client:
    def __init__(self, auth_header: str, base_url: str | None = None):
        self.auth_header = auth_header
        self.base_url = base_url or settings.trading212_base_url

    async def _request(self, method: str, path: str) -> dict | list:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": self.auth_header},
                timeout=30.0,
            )
            if response.status_code == 401:
                raise PermissionError("401 Unauthorized — credentials may be invalid or revoked")
            response.raise_for_status()
            return response.json()

    async def fetch_positions(self) -> list[Trading212Position]:
        data = await self._request("GET", "/equity/portfolio")
        return [
            Trading212Position(
                ticker=item["ticker"],
                quantity=item["quantity"],
                average_price=item["averagePrice"],
                current_price=item["currentPrice"],
                ppl=item.get("ppl", 0.0),
                fx_ppl=item.get("fxPpl", 0.0),
            )
            for item in data
        ]

    async def verify_key(self) -> bool:
        try:
            await self._request("GET", "/equity/account/cash")
            return True
        except (PermissionError, httpx.HTTPStatusError):
            return False


async def detect_trading212_base_url(auth_header: str) -> str | None:
    """Try live then demo to find which environment the credentials belong to."""
    for url in (_LIVE_URL, _DEMO_URL):
        client = Trading212Client(auth_header=auth_header, base_url=url)
        if await client.verify_key():
            return url
    return None
