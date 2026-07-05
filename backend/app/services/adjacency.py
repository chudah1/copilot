"""Adjacency evidence: items the LLM relevance filter reviewed and ruled out.

Powers the "we looked at these and decided they didn't rise to an alert"
surface — in the weekly digest and in the position monitoring tab. The
whole point of quiet products is proof of watchfulness, so this module
turns the coverage_pass drops into a curated, reader-facing block.

Kept separate from digest_builder / route modules so both surfaces call
the same loader + curator + labels.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage_pass import CoveragePass


# Sources we consider trusted / editorially curated. When we can only surface
# a couple of drops, these beat generic yfinance headlines on the tiebreaker.
_TRUSTED_DROP_SOURCES = {"gemini_news", "edgar_8k"}


# Reader-facing labels for internal source enums. Never leak the raw enum
# ("gemini_news") to a user — they don't know what Gemini is and shouldn't
# have to. Publisher name from the URL is preferred over these; this is only
# the fallback when we don't have a URL to parse.
_SOURCE_FALLBACK_LABELS = {
    "gemini_news": "web news",
    "news_or_earnings_candidate": "news",
    "news_keyword_match": "news",
    "product_ramp_update": "news",
    "contract_renewal_update": "news",
    "funding_condition_update": "news",
    "margin_pressure_update": "news",
    "customer_capex_signal": "news",
    "edgar_8k": "SEC filing",
    "edgar_form4": "insider filing",
    "earnings_call_transcript": "earnings call",
    "earnings_surprise": "earnings report",
}


# Publisher domains we recognize and want to render with a clean name rather
# than the parsed root domain. Anything not in this table falls back to
# capitalizing the first label of the domain, which is fine for most sites.
_PUBLISHER_DOMAIN_LABELS = {
    "reuters.com": "Reuters",
    "bloomberg.com": "Bloomberg",
    "wsj.com": "WSJ",
    "ft.com": "FT",
    "cnbc.com": "CNBC",
    "seekingalpha.com": "Seeking Alpha",
    "barrons.com": "Barron's",
    "marketwatch.com": "MarketWatch",
    "nytimes.com": "NY Times",
    "washingtonpost.com": "Washington Post",
    "theverge.com": "The Verge",
    "techcrunch.com": "TechCrunch",
    "sec.gov": "SEC",
    "prnewswire.com": "PR Newswire",
    "businesswire.com": "Business Wire",
    "fool.com": "Motley Fool",
    "investing.com": "Investing.com",
    "yahoo.com": "Yahoo Finance",
    "finance.yahoo.com": "Yahoo Finance",
}


def source_label_for_reader(source: str | None, url: str | None) -> str:
    """Turn an internal source enum + optional URL into a label the user
    can read. Publisher name (Reuters, Bloomberg, SEC) beats a generic
    category label, which beats a raw enum. Never returns the raw enum
    directly — users shouldn't see 'gemini_news' or 'news_or_earnings_candidate'
    in the UI."""
    if url:
        publisher = _publisher_from_url(url)
        if publisher:
            return publisher
    if source:
        friendly = _SOURCE_FALLBACK_LABELS.get(source)
        if friendly:
            return friendly
    return "news"


def _publisher_from_url(url: str) -> str | None:
    """Extract a display-worthy publisher name from a URL. Returns None on
    unparseable or empty URLs, so callers can fall back to a source label."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().strip()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if host in _PUBLISHER_DOMAIN_LABELS:
        return _PUBLISHER_DOMAIN_LABELS[host]
    # Try one level up — some publishers use subdomains like uk.reuters.com.
    parts = host.split(".")
    if len(parts) >= 3:
        base = ".".join(parts[-2:])
        if base in _PUBLISHER_DOMAIN_LABELS:
            return _PUBLISHER_DOMAIN_LABELS[base]
    # Fallback: capitalize the first meaningful token of the domain
    # ("techcrunch.com" → "Techcrunch"). Not perfect but never
    # user-hostile.
    if len(parts) >= 2:
        first_label = parts[0] if parts[0] != "www" else parts[1]
        first_label = first_label.strip().replace("-", " ")
        if first_label:
            return first_label[:1].upper() + first_label[1:]
    return None


async def load_reviewed_but_dropped(
    db: AsyncSession,
    *,
    thesis_ids: list[uuid.UUID],
    ticker_by_thesis: dict[str, str],
    holding_id_by_thesis: dict[str, uuid.UUID],
    period_start: datetime,
    period_end: datetime,
) -> list[dict[str, Any]]:
    """Pull reviewed-but-dropped items across the given theses in a window.

    Flattens the coverage_pass payloads, tags each item with ticker + holding,
    and dedupes on URL and (ticker, headline) so the same article dropped in
    two passes shows once.
    """
    if not thesis_ids:
        return []

    result = await db.execute(
        select(CoveragePass)
        .where(
            CoveragePass.thesis_id.in_(thesis_ids),
            CoveragePass.started_at >= period_start,
            CoveragePass.started_at <= period_end,
        )
        .order_by(CoveragePass.started_at.desc())
    )
    passes = list(result.scalars().all())

    seen_urls: set[str] = set()
    seen_headline_keys: set[tuple[str, str]] = set()
    flat: list[dict[str, Any]] = []
    for pass_row in passes:
        payload = pass_row.payload or {}
        if not isinstance(payload, dict):
            continue
        drops = payload.get("reviewed_but_dropped")
        if not isinstance(drops, list):
            continue
        thesis_key = str(pass_row.thesis_id)
        ticker = ticker_by_thesis.get(thesis_key)
        holding_id = holding_id_by_thesis.get(thesis_key)
        if not ticker or holding_id is None:
            continue
        for drop in drops:
            if not isinstance(drop, dict):
                continue
            headline = (drop.get("headline") or "").strip()
            reason = (drop.get("reason") or "").strip()
            if not headline or not reason:
                continue
            url = (drop.get("url") or "").strip()
            headline_key = (ticker, headline.lower())
            if url and url in seen_urls:
                continue
            if headline_key in seen_headline_keys:
                continue
            if url:
                seen_urls.add(url)
            seen_headline_keys.add(headline_key)
            raw_source = drop.get("source") or ""
            flat.append({
                "ticker": ticker,
                "holding_id": str(holding_id),
                "headline": headline,
                "reason": reason,
                "source": raw_source,
                "source_label": source_label_for_reader(raw_source, url or None),
                "url": url or None,
                "published_at": drop.get("published_at"),
                "matched_signal_labels": drop.get("matched_signal_labels") or [],
                "pass_started_at": pass_row.started_at,
            })
    return flat


# Default cap on how many items any single surface (digest section, position
# tab) shows. The point is a taste of "we looked," not a receipt of every
# filter decision — small numbers keep the section skimmable.
DEFAULT_MAX_REVIEWED_ITEMS = 2


def curate_reviewed_but_dropped(
    drops: list[dict[str, Any]],
    *,
    holdings_covered: set[str] | None = None,
    max_items: int = DEFAULT_MAX_REVIEWED_ITEMS,
    require_distinct_tickers: bool = True,
) -> list[dict[str, Any]]:
    """Pick the strongest N reviewed-but-dropped items.

    Preferences:
      - substantive reasons (short generic strings are noise)
      - close-call items (matched_signal_labels non-empty) — the LLM saw
        a thesis connection but ruled it out, which is the interesting shape
      - trusted sources (Gemini / EDGAR) over generic yfinance news
    Constraints:
      - one per ticker by default (require_distinct_tickers) — dashboard/
        digest surfaces want breadth; the per-position surface passes False
        so it can show multiple items for the same ticker
      - skip tickers already covered by a live alert (holdings_covered);
        the alert is louder and the receipt shouldn't compete
    """
    if not drops:
        return []

    def _sort_timestamp(item: dict[str, Any]) -> int:
        for key in ("published_at", "pass_started_at"):
            raw = item.get(key)
            if isinstance(raw, datetime):
                dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            if isinstance(raw, str) and raw:
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return int(dt.timestamp())
                except ValueError:
                    continue
        return 0

    def _score(item: dict[str, Any]) -> tuple[int, int, int, int]:
        reason_len = len(item.get("reason") or "")
        substantive = 1 if reason_len >= 40 else 0
        trusted = 1 if item.get("source") in _TRUSTED_DROP_SOURCES else 0
        close_call = 1 if item.get("matched_signal_labels") else 0
        recency = _sort_timestamp(item)
        return (substantive, trusted, close_call, recency)

    covered = set(holdings_covered or set())
    sorted_drops = sorted(drops, key=_score, reverse=True)
    picked: list[dict[str, Any]] = []
    picked_tickers: set[str] = set()
    for item in sorted_drops:
        if len(picked) >= max_items:
            break
        ticker = item.get("ticker")
        if not ticker:
            continue
        if ticker in covered:
            continue
        if require_distinct_tickers and ticker in picked_tickers:
            continue
        # Filter out reasons that came back too terse to be useful.
        if len(item.get("reason") or "") < 20:
            continue
        picked_tickers.add(ticker)
        picked.append(item)
    return picked
