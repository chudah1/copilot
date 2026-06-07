"""Gemini Flash news collector — two-step search + structured extraction.

Step 1: call Gemini with Google Search grounding and ask for unstructured
        markdown. Grounding mode reliably triggers searches but fights JSON.
Step 2: pass the raw markdown to a second call with response_schema enforced.
        Structured-output mode guarantees schema compliance but has no search.

Silently returns [] on any failure — news collection is enrichment, not
critical path.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

MAX_SIGNALS = 12
_GEMINI_MODEL = "gemini-2.5-flash"


class _NewsArticle(BaseModel):
    headline: str = Field(description="Exact article headline")
    url: str = Field(description="Full destination URL")
    date: str = Field(description="Publication date as YYYY-MM-DD")
    summary: str = Field(description="1-2 sentence summary of what happened")
    relevant_signals: list[str] = Field(description="Signal labels from the provided list that this article matches")
    relevance: str = Field(description="One of: high, medium, low")


class _NewsResponse(BaseModel):
    articles: list[_NewsArticle]


async def collect_news_evidence(
    ticker: str,
    name: str,
    signal_labels: list[str],
) -> list[dict[str, Any]]:
    """Return gemini_news monitoring candidates for the given ticker and signals."""
    if not settings.gemini_api_key or not signal_labels:
        return []

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai SDK not installed — skipping news collection")
        return []

    signals_text = "\n".join(f"- {label}" for label in signal_labels[:MAX_SIGNALS])

    now = datetime.now(timezone.utc)
    since_str = (now - timedelta(days=7)).strftime("%B %-d, %Y")
    until_str = now.strftime("%B %-d, %Y")

    search_prompt = f"""\
Search for news articles published between {since_str} and {until_str} about {name} (ticker: {ticker}).

Find articles directly relevant to one or more of these investment signals:
{signals_text}

For every relevant article write a structured markdown entry with:
- HEADLINE: [exact article title]
- URL: [full destination URL]
- DATE: [YYYY-MM-DD]
- SUMMARY: [1-2 sentence description of what happened]
- SIGNALS: [which of the listed signals this matches]

If no relevant articles exist in that date range, write exactly: No news found.\
"""

    extraction_prompt_template = """\
You are a financial data parser. Extract structured news records from the raw search results below.

Company: __NAME__ (__TICKER__)

Date range: __SINCE__ to __UNTIL__

Investment signals (use exact label text when matching):
__SIGNALS__

Raw search results:
__RAW__

Extract every article that is relevant to at least one listed signal. \
Discard anything outside the stated date range (__SINCE__ to __UNTIL__) or unrelated to the signals.\
"""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        # Step 1 — search with grounding, unstructured output
        search_response = await asyncio.to_thread(
            client.models.generate_content,
            model=_GEMINI_MODEL,
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
            ),
        )

        raw_text = (getattr(search_response, "text", "") or "").strip()
        if not raw_text or raw_text.lower().startswith("no news found"):
            return []

        # Collect grounding metadata for is_grounded tagging
        grounded_urls: set[str] = set()
        try:
            metadata = search_response.candidates[0].grounding_metadata
            if metadata and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if chunk.web and chunk.web.uri:
                        grounded_urls.add(chunk.web.uri)
        except (AttributeError, IndexError, TypeError):
            pass

        # Step 2 — structured extraction, no search
        extraction_prompt = (
            extraction_prompt_template
            .replace("__NAME__", name)
            .replace("__TICKER__", ticker)
            .replace("__SINCE__", since_str)
            .replace("__UNTIL__", until_str)
            .replace("__SIGNALS__", signals_text)
            .replace("__RAW__", raw_text)
        )
        extraction_response = await asyncio.to_thread(
            client.models.generate_content,
            model=_GEMINI_MODEL,
            contents=extraction_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=_NewsResponse,
            ),
        )

        extraction_text = (getattr(extraction_response, "text", "") or "").strip()
        parsed = json.loads(extraction_text)
        items = (parsed.get("articles") or []) if isinstance(parsed, dict) else (parsed or [])

        return _to_candidates(items, grounded_urls)

    except Exception as exc:
        logger.warning("Gemini news collection failed for %s: %s", ticker, exc)
        return []


def _to_candidates(
    items: list[dict],
    grounded_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    if grounded_urls is None:
        grounded_urls = set()

    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = (item.get("headline") or "").strip()
        if not headline:
            continue
        url = item.get("url") or item.get("source_url") or ""
        summary = (item.get("summary") or "").strip()
        relevant_signals = item.get("relevant_signals")
        if not isinstance(relevant_signals, list):
            relevant_signals = []

        article_id = hashlib.sha256(f"{headline}{url}".encode()).hexdigest()[:16]

        candidates.append({
            "event_type": "gemini_news",
            "description": f"{headline} — {summary}" if summary else headline,
            "evidence": {
                "article_id": article_id,
                "headline": headline,
                "summary": summary,
                "url": url or None,
                "date": item.get("date"),
                "relevant_signals": relevant_signals,
                "relevance": item.get("relevance", "medium"),
                "source": "gemini_search",
                "is_grounded": bool(url and url in grounded_urls),
            },
        })
    return candidates
