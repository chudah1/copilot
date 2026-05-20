"""EDGAR (SEC) filing client.

Polls the SEC submissions API for 8-K filings and Form 4 insider transactions
for US-listed tickers. No API key required; SEC policy requires a User-Agent.
Rate limit: 10 requests/second — well within normal usage.
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
SEC_BASE = "https://www.sec.gov"
TICKERS_URL = f"{SEC_BASE}/files/company_tickers.json"
EDGAR_LOOKBACK_DAYS = 7

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


@dataclass
class EdgarFiling:
    form_type: str  # "8-K" or "8-K/A"
    filing_date: date
    accession_number: str  # e.g. "0001193125-25-012345"
    items: list[str]  # e.g. ["2.02", "9.01"]
    document_url: str
    description: str  # human-readable item summary


async def _load_ticker_cik_map() -> dict[str, str]:
    global _ticker_cik_cache
    async with _ticker_cik_lock:
        if _ticker_cik_cache is not None:
            return _ticker_cik_cache
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                TICKERS_URL,
                headers={"User-Agent": settings.edgar_user_agent},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
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

    url = f"{EDGAR_BASE}/submissions/CIK{cik.zfill(10)}.json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={"User-Agent": settings.edgar_user_agent},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("EDGAR request failed for %s: %s", ticker, exc)
        return []

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

    url = f"{EDGAR_BASE}/submissions/CIK{cik.zfill(10)}.json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"User-Agent": settings.edgar_user_agent}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
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
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    doc_url, headers={"User-Agent": settings.edgar_user_agent}, timeout=15
                )
                resp.raise_for_status()
                xml_text = resp.text
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
