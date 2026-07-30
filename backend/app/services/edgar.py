"""EDGAR (SEC) filing client.

Polls the SEC submissions API for 8-K filings and Form 4 insider transactions
for US-listed tickers. All SEC traffic goes through one conservative request
budget so scheduled and manual checks cannot burst past the SEC's fair-access
limit.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
SEC_BASE = "https://www.sec.gov"
TICKERS_URL = f"{SEC_BASE}/files/company_tickers.json"
EDGAR_LOOKBACK_DAYS = 7
_SUBMISSIONS_CACHE_TTL_SECONDS = 15 * 60
_SUBMISSIONS_CACHE_MAX_ENTRIES = 128
_REQUESTS_PER_SECOND = 5
_MIN_REQUEST_INTERVAL_SECONDS = 1 / _REQUESTS_PER_SECOND
_MAX_REQUEST_ATTEMPTS = 4
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER_SECONDS = 60.0

# 8-K items that are investment-relevant
MATERIAL_8K_ITEMS: dict[str, str] = {
    "1.01": "Material Agreement",
    "1.02": "Agreement Termination",
    "1.03": "Bankruptcy or Receivership",
    "2.01": "Acquisition or Disposal",
    "2.02": "Earnings Release",
    "2.05": "Restructuring",
    "2.06": "Material Impairment",
    "4.02": "Non-Reliance on Financials",
    "5.02": "Executive Change",
    "7.01": "Guidance / Reg FD",
    "8.01": "Other Material Event",
}

# Administrative items that appear in almost every 8-K but carry no signal alone
_ADMIN_ONLY_ITEMS = {"9.01"}

_ticker_cik_cache: dict[str, str] | None = None
_ticker_cik_lock = asyncio.Lock()
_submissions_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_submissions_inflight: dict[str, asyncio.Task[dict[str, Any]]] = {}
_submissions_lock = asyncio.Lock()
_http_client: httpx.AsyncClient | None = None
_http_client_lock = asyncio.Lock()
_request_slot_lock = asyncio.Lock()
_last_request_started_at = 0.0


@dataclass
class EdgarFiling:
    form_type: str  # "8-K" or "8-K/A"
    filing_date: date
    accession_number: str  # e.g. "0001193125-25-012345"
    items: list[str]  # e.g. ["2.02", "9.01"]
    document_url: str
    description: str  # human-readable item summary


async def _get_http_client() -> httpx.AsyncClient:
    """Return the one connection-pooled client used for all SEC requests."""
    global _http_client
    async with _http_client_lock:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.AsyncClient(
                headers={
                    "User-Agent": settings.edgar_user_agent,
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=20,
                follow_redirects=True,
            )
        return _http_client


async def close_edgar_client() -> None:
    """Close the shared SEC connection pool during application shutdown."""
    global _http_client
    async with _http_client_lock:
        client = _http_client
        _http_client = None
    if client is not None and not client.is_closed:
        await client.aclose()


async def _wait_for_request_slot() -> None:
    """Space SEC request starts to a conservative five requests per second."""
    global _last_request_started_at
    async with _request_slot_lock:
        now = time.monotonic()
        delay = _MIN_REQUEST_INTERVAL_SECONDS - (now - _last_request_started_at)
        if delay > 0:
            await asyncio.sleep(delay)
        _last_request_started_at = time.monotonic()


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Use Retry-After when supplied, otherwise exponential backoff plus jitter."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), _MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
                return min(max(seconds, 0.0), _MAX_RETRY_AFTER_SECONDS)
            except (TypeError, ValueError, OverflowError):
                pass
    return min((2 ** attempt) + random.uniform(0, 0.25), _MAX_RETRY_AFTER_SECONDS)


async def _request(url: str) -> httpx.Response:
    """Fetch one SEC URL with global throttling and transient-error retries."""
    client = await _get_http_client()
    response: httpx.Response | None = None
    for attempt in range(_MAX_REQUEST_ATTEMPTS):
        await _wait_for_request_slot()
        try:
            response = await client.get(url)
        except httpx.TransportError as exc:
            if attempt == _MAX_REQUEST_ATTEMPTS - 1:
                raise
            delay = min((2 ** attempt) + random.uniform(0, 0.25), 8.0)
            logger.warning(
                "SEC transport error; retrying in %.2fs (%d/%d): %s",
                delay,
                attempt + 1,
                _MAX_REQUEST_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(delay)
            continue

        if response.status_code not in _TRANSIENT_STATUS_CODES:
            response.raise_for_status()
            return response
        if attempt == _MAX_REQUEST_ATTEMPTS - 1:
            response.raise_for_status()
        delay = _retry_delay(response, attempt)
        logger.warning(
            "SEC returned %d; retrying in %.2fs (%d/%d): %s",
            response.status_code,
            delay,
            attempt + 1,
            _MAX_REQUEST_ATTEMPTS,
            url,
        )
        await asyncio.sleep(delay)

    if response is not None:  # Defensive: the loop always returns or raises.
        response.raise_for_status()
    raise RuntimeError(f"SEC request failed without a response: {url}")


async def _request_json(url: str) -> dict[str, Any]:
    response = await _request(url)
    return response.json()


async def fetch_sec_text(url: str) -> str:
    """Fetch text from an SEC-owned URL through the shared request budget."""
    if not url.startswith((f"{SEC_BASE}/", f"{EDGAR_BASE}/")):
        raise ValueError("fetch_sec_text only accepts SEC URLs")
    response = await _request(url)
    return response.text


async def _fetch_and_cache_submissions(cik: str) -> dict[str, Any]:
    url = f"{EDGAR_BASE}/submissions/CIK{cik.zfill(10)}.json"
    data = await _request_json(url)
    async with _submissions_lock:
        _submissions_cache[cik] = (time.monotonic(), data)
        if len(_submissions_cache) > _SUBMISSIONS_CACHE_MAX_ENTRIES:
            oldest_cik = min(
                _submissions_cache,
                key=lambda cached_cik: _submissions_cache[cached_cik][0],
            )
            _submissions_cache.pop(oldest_cik, None)
    return data


async def _get_submissions(cik: str) -> dict[str, Any]:
    """Return one cached/coalesced submissions payload per CIK."""
    normalized_cik = str(int(cik))
    now = time.monotonic()
    async with _submissions_lock:
        expired = [
            cached_cik
            for cached_cik, (cached_at, _) in _submissions_cache.items()
            if now - cached_at >= _SUBMISSIONS_CACHE_TTL_SECONDS
        ]
        for cached_cik in expired:
            _submissions_cache.pop(cached_cik, None)

        cached = _submissions_cache.get(normalized_cik)
        if cached:
            return cached[1]

        task = _submissions_inflight.get(normalized_cik)
        if task is None:
            task = asyncio.create_task(_fetch_and_cache_submissions(normalized_cik))
            _submissions_inflight[normalized_cik] = task

    try:
        return await asyncio.shield(task)
    finally:
        if task.done():
            async with _submissions_lock:
                if _submissions_inflight.get(normalized_cik) is task:
                    _submissions_inflight.pop(normalized_cik, None)


async def _load_ticker_cik_map() -> dict[str, str]:
    global _ticker_cik_cache
    async with _ticker_cik_lock:
        if _ticker_cik_cache is not None:
            return _ticker_cik_cache
        data = await _request_json(TICKERS_URL)
        _ticker_cik_cache = {v["ticker"].upper(): str(v["cik_str"]) for v in data.values()}
        return _ticker_cik_cache


async def get_cik_for_ticker(ticker: str) -> str | None:
    clean = ticker.replace("_US_EQ", "").replace("_EQ", "").upper()
    try:
        mapping = await _load_ticker_cik_map()
        return mapping.get(clean)
    except Exception as exc:
        logger.warning("Failed to load EDGAR ticker→CIK map: %s", exc)
        return None


def _filing_url(cik: str, accession: str, primary_doc: str) -> str:
    accession_clean = accession.replace("-", "")
    if primary_doc:
        # Strip EDGAR XSL stylesheet prefix (e.g. "xslF345X06/ownership.xml" → "ownership.xml")
        doc = primary_doc.split("/")[-1] if primary_doc.startswith("xsl") else primary_doc
        return f"{SEC_BASE}/Archives/edgar/data/{cik}/{accession_clean}/{doc}"
    return f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcompany&CIK={cik.zfill(10)}&type=8-K"


def _is_material(items: list[str]) -> bool:
    """True if the filing has at least one item beyond administrative exhibits."""
    return any(i not in _ADMIN_ONLY_ITEMS for i in items)


def _describe_items(items: list[str]) -> str:
    labels = [MATERIAL_8K_ITEMS[i] for i in items if i in MATERIAL_8K_ITEMS]
    return ", ".join(labels) if labels else "Material Event"


async def get_recent_8k_filings(ticker: str, since: date | None = None) -> list[EdgarFiling]:
    """Return 8-K filings for ticker filed on or after `since` (default: 7 days ago)."""
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=EDGAR_LOOKBACK_DAYS)).date()

    cik = await get_cik_for_ticker(ticker)
    if not cik:
        return []

    try:
        data = await _get_submissions(cik)
    except Exception as exc:
        logger.warning("EDGAR request failed for %s: %s", ticker, exc)
        raise

    recent = data.get("filings", {}).get("recent", {})
    forms: list[str] = recent.get("form", [])
    filing_dates: list[str] = recent.get("filingDate", [])
    accessions: list[str] = recent.get("accessionNumber", [])
    primary_docs: list[str] = recent.get("primaryDocument", [])
    items_raw: list[str] = recent.get("items", [])

    filings: list[EdgarFiling] = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        try:
            filing_date = date.fromisoformat(filing_dates[i])
        except (ValueError, IndexError):
            continue
        if filing_date < since:
            break  # EDGAR returns filings in reverse chronological order

        accession = accessions[i] if i < len(accessions) else ""
        primary_doc = primary_docs[i] if i < len(primary_docs) else ""
        items_str = items_raw[i] if i < len(items_raw) else ""
        items = [item.strip() for item in items_str.split(",") if item.strip()]

        if not _is_material(items):
            continue

        filings.append(EdgarFiling(
            form_type=form,
            filing_date=filing_date,
            accession_number=accession,
            items=items,
            document_url=_filing_url(cik, accession, primary_doc),
            description=_describe_items(items),
        ))

    return filings


def build_edgar_candidates(ticker: str, filings: list[EdgarFiling]) -> list[dict[str, Any]]:
    """Convert EDGAR filings into monitoring candidate dicts."""
    clean = ticker.replace("_US_EQ", "").replace("_EQ", "")
    return [
        {
            "event_type": "edgar_8k",
            "description": f"SEC 8-K filed by {clean}: {f.description} ({f.filing_date})",
            "evidence": {
                "url": f.document_url,
                "edgar_accession": f.accession_number,
                "filing_date": f.filing_date.isoformat(),
                "form_type": f.form_type,
                "items": f.items,
                "description": f.description,
            },
        }
        for f in filings
    ]


# ---------------------------------------------------------------------------
# Form 4 — insider transactions
# ---------------------------------------------------------------------------

# Only open-market discretionary trades — exclude option exercises (M/X),
# gifts (G), tax withholding (F), awards (A), and other non-discretionary codes.
_F4_OPEN_MARKET: dict[str, str] = {
    "S": "Open market sale",
    "P": "Open market purchase",
}


def _xml_val(element: ET.Element, *tags: str) -> str | None:
    """Find the first matching tag's <value> text in an XML element."""
    for tag in tags:
        el = element.find(f".//{tag}/value")
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
        el = element.find(f".//{tag}")
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
    return None


def _parse_form4_xml(
    xml_text: str,
    accession: str,
    filing_date: date,
) -> list[dict[str, Any]]:
    """Parse Form 4 XML into insider transaction dicts. Returns [] on any error."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    owner_name = _xml_val(root, "rptOwnerName") or "Unknown"
    owner_title = _xml_val(root, "officerTitle") or ""

    # Only process directors, officers, 10%+ owners
    if not (
        _xml_val(root, "isOfficer") == "1"
        or _xml_val(root, "isDirector") == "1"
        or _xml_val(root, "isTenPercentOwner") == "1"
    ):
        return []

    filing_dt = datetime.combine(filing_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    transactions = []

    for i, txn in enumerate(root.findall(".//nonDerivativeTransaction")):
        code = _xml_val(txn, "transactionCode") or ""
        if code not in _F4_OPEN_MARKET:
            continue

        date_str = _xml_val(txn, "transactionDate")
        shares_str = _xml_val(txn, "transactionShares")
        price_str = _xml_val(txn, "transactionPricePerShare")

        try:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) if date_str else filing_dt
        except ValueError:
            txn_date = filing_dt

        try:
            shares = float(shares_str) if shares_str else None
        except ValueError:
            shares = None

        try:
            price = float(price_str) if price_str else None
        except ValueError:
            price = None

        transactions.append({
            "id": f"{accession}_{i}",
            "filing_date": filing_dt,
            "transaction_date": txn_date,
            "insider_name": owner_name,
            "title": owner_title,
            "transaction_type": _F4_OPEN_MARKET[code],
            "shares": shares,
            "share_price": price,
            "value": shares * price if shares and price else None,
        })

    return transactions


async def get_recent_form4_transactions(ticker: str, since: date | None = None) -> list[dict[str, Any]]:
    """Fetch and parse Form 4 insider transactions from EDGAR."""
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=EDGAR_LOOKBACK_DAYS)).date()

    cik = await get_cik_for_ticker(ticker)
    if not cik:
        return []

    try:
        data = await _get_submissions(cik)
    except Exception as exc:
        logger.warning("EDGAR Form 4 submissions fetch failed for %s: %s", ticker, exc)
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms: list[str] = recent.get("form", [])
    filing_dates: list[str] = recent.get("filingDate", [])
    accessions: list[str] = recent.get("accessionNumber", [])
    primary_docs: list[str] = recent.get("primaryDocument", [])

    transactions: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if form not in ("4", "4/A"):
            continue
        try:
            filing_date = date.fromisoformat(filing_dates[i])
        except (ValueError, IndexError):
            continue
        if filing_date < since:
            break

        accession = accessions[i] if i < len(accessions) else ""
        primary_doc = primary_docs[i] if i < len(primary_docs) else ""
        doc_url = _filing_url(cik, accession, primary_doc)

        try:
            xml_text = await fetch_sec_text(doc_url)
        except Exception as exc:
            logger.warning("Failed to fetch Form 4 document %s: %s", doc_url, exc)
            continue

        parsed = _parse_form4_xml(xml_text, accession, filing_date)
        transactions.extend(parsed)

    return transactions


def build_form4_candidates(
    ticker: str, transactions: list[dict[str, Any]], *, now: datetime
) -> list[dict[str, Any]]:
    """Convert Form 4 transaction dicts into monitoring candidate dicts.

    Groups same-insider same-day transactions to avoid N candidates per
    chunked trade (brokers often split one decision into many lots).
    """
    # Group by (insider_name, transaction_date_date, transaction_type)
    groups: dict[tuple, dict[str, Any]] = {}
    for txn in transactions:
        txn_date = txn["transaction_date"] or txn["filing_date"]
        if txn_date is None or txn_date < now - timedelta(days=30):
            continue
        key = (txn["insider_name"], txn_date.date(), txn["transaction_type"])
        if key not in groups:
            groups[key] = {**txn, "transaction_date": txn_date, "_total_shares": 0.0, "_total_value": 0.0}
        g = groups[key]
        if txn.get("shares"):
            g["_total_shares"] += txn["shares"]
        if txn.get("value"):
            g["_total_value"] += txn["value"]

    candidates = []
    for (_, txn_date, _), g in groups.items():
        txn_type = g["transaction_type"].lower()
        if any(k in txn_type for k in ("sale", "sell")):
            direction = "sale"
        elif any(k in txn_type for k in ("purchase", "acqui")):
            direction = "purchase"
        else:
            continue

        total_shares = g["_total_shares"] or None
        total_value = g["_total_value"] or None
        shares_text = f"{total_shares:,.0f} shares" if total_shares else "shares"
        title = g.get("title", "")

        # Use accession of first transaction in group as the dedup key
        candidates.append({
            "event_type": "insider_transaction",
            "description": (
                f"{g['insider_name'] or 'An insider'}"
                f"{f' ({title})' if title else ''} reported a {direction} of {shares_text}."
            ),
            "evidence": {
                "transaction_id": g["id"],
                "transaction_date": txn_date.isoformat(),
                "filing_date": g["filing_date"].isoformat() if g.get("filing_date") else None,
                "insider_name": g["insider_name"],
                "title": title,
                "transaction_type": g["transaction_type"],
                "shares": total_shares,
                "share_price": g.get("share_price"),
                "value": total_value if total_value else g.get("value"),
            },
        })

    return candidates
