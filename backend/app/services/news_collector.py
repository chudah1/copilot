"""Gemini Flash news collector — two-step search + structured extraction.

Step 1: call Gemini with Google Search grounding and ask for unstructured
        markdown. Grounding mode reliably triggers searches but fights JSON.
Step 2: pass the raw markdown to a second call with response_schema enforced.
        Structured-output mode guarantees schema compliance but has no search.

Re-raises exceptions on failure — callers are responsible for catching and
writing a MonitoringGap record. Returns [] only when the API key is absent
or no signal labels are provided (non-error fast-paths).
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
from app.services.news_watch import expand_watch_queries

logger = logging.getLogger(__name__)

MAX_SIGNALS = 12
_GEMINI_MODEL = "gemini-2.5-flash"
_MAX_FOCUSED_SIGNAL_SEARCHES = 3
_ROUNDUP_NOISE_PATTERNS: tuple[str, ...] = (
    "stocks to buy",
    "stocks to watch",
    "stock is up today",
    "stock is down today",
    "next nvidia",
    "top stocks",
    "best stocks",
    "market recap",
    "weekly roundup",
    "roundup",
    "wallstreetbets",
    "buzzing about",
)
_LOW_RELEVANCE_VALUES = {"low"}
_FOCUSED_SIGNAL_HINTS: tuple[str, ...] = (
    "commentary",
    "guidance",
    "share",
    "renewal",
    "deployment",
    "ramp",
    "demand",
    "adoption",
    "funding",
    "margin",
    "capex",
    "backlog",
    "underwriting",
    "delinquency",
    "payoff",
    "customer",
)


class _NewsArticle(BaseModel):
    headline: str = Field(description="Exact article headline")
    url: str = Field(description="Full destination URL")
    date: str = Field(description="Publication date as YYYY-MM-DD")
    summary: str = Field(description="1-2 sentence summary of what happened")
    relevant_signals: list[str] = Field(description="Signal labels from the provided list that this article matches")
    relevance: str = Field(description="One of: high, medium, low")


class _NewsResponse(BaseModel):
    articles: list[_NewsArticle]


def _normalise_signal_search_inputs(signal_inputs: list[Any]) -> list[dict[str, str]]:
    descriptors: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in signal_inputs[:MAX_SIGNALS]:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            claim_text = str(item.get("claim_text") or "").strip()
            rationale = str(item.get("rationale") or "").strip()
        else:
            label = str(item or "").strip()
            claim_text = ""
            rationale = ""
        if not label:
            continue
        normalized = label.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        descriptors.append(
            {
                "label": label,
                "claim_text": claim_text,
                "rationale": rationale,
            }
        )
    return descriptors


def _signal_search_bullets(signal_inputs: list[Any]) -> str:
    lines: list[str] = []
    for descriptor in _normalise_signal_search_inputs(signal_inputs):
        label = descriptor["label"]
        variants = expand_watch_queries(label)
        details: list[str] = []
        if descriptor["claim_text"]:
            details.append(f"claim: {descriptor['claim_text']}")
        if descriptor["rationale"]:
            details.append(f"why it matters: {descriptor['rationale']}")
        if len(variants) > 1:
            details.append(f"alternate phrasings: {', '.join(variants[1:4])}")
        if details:
            lines.append(f"- {label} | {' | '.join(details)}")
        else:
            lines.append(f"- {label}")
    return "\n".join(lines)


def _focused_signal_score(descriptor: dict[str, str]) -> tuple[int, int, int]:
    label = descriptor["label"]
    lowered = f"{label} {descriptor.get('claim_text', '')} {descriptor.get('rationale', '')}".lower()
    keyword_hits = sum(1 for hint in _FOCUSED_SIGNAL_HINTS if hint in lowered)
    word_count = len(label.split())
    context_words = len(descriptor.get("claim_text", "").split()) + len(descriptor.get("rationale", "").split())
    return keyword_hits, context_words, word_count


def _select_focused_signal_labels(signal_inputs: list[Any]) -> list[dict[str, str]]:
    cleaned = _normalise_signal_search_inputs(signal_inputs)
    ranked = sorted(
        cleaned,
        key=lambda descriptor: (
            _focused_signal_score(descriptor),
            len(expand_watch_queries(descriptor["label"])),
            len(descriptor["label"]),
        ),
        reverse=True,
    )
    return ranked[:_MAX_FOCUSED_SIGNAL_SEARCHES]


def _focused_signal_prompt(
    *,
    ticker: str,
    name: str,
    signal: dict[str, str],
    since_str: str,
    until_str: str,
) -> str:
    signal_label = signal["label"]
    claim_text = signal.get("claim_text", "").strip()
    rationale = signal.get("rationale", "").strip()
    variants = expand_watch_queries(signal_label)
    alternate_text = ""
    if len(variants) > 1:
        alternate_text = f"\nAlternate phrasings to treat as equivalent: {', '.join(variants[1:4])}"
    claim_text_block = f"\nUnderlying claim: {claim_text}" if claim_text else ""
    rationale_block = f"\nWhy this matters: {rationale}" if rationale else ""

    return f"""\
Search for news articles published between {since_str} and {until_str} about {name} (ticker: {ticker}) specifically tied to this investment signal:
- {signal_label}{alternate_text}{claim_text_block}{rationale_block}

Only include articles where {name} or {ticker} is a primary subject.
Prioritize discrete business updates, management commentary, customer announcements, press releases,
earnings-call coverage, or Reuters/Bloomberg-style reporting that directly bears on this signal.
Exclude broad stock roundups, market recaps, "why this stock is up/down today" explainers,
peer-comparison lists, or articles where the company is only mentioned in passing.

For every relevant article write a structured markdown entry with:
- HEADLINE: [exact article title]
- URL: [full destination URL]
- DATE: [YYYY-MM-DD]
- SUMMARY: [1-2 sentence description of what happened]
- SIGNALS: [which of the listed signals this matches]

If no relevant articles exist in that date range, write exactly: No news found.\
"""


def _looks_like_roundup_noise(headline: str, summary: str) -> bool:
    text = f"{headline} {summary}".lower()
    return any(pattern in text for pattern in _ROUNDUP_NOISE_PATTERNS)


def _topic_context_from_relevant_signals(relevant_signals: list[str]) -> tuple[list[str], str]:
    matched_topics: list[str] = []
    for label in relevant_signals[:4]:
        for variant in expand_watch_queries(label)[:2]:
            cleaned = variant.strip()
            if cleaned and cleaned not in matched_topics:
                matched_topics.append(cleaned)
            if len(matched_topics) >= 6:
                return matched_topics, ", ".join(matched_topics)
    return matched_topics, ", ".join(matched_topics)


async def _run_grounded_search(
    client: Any,
    *,
    prompt: str,
) -> tuple[str, set[str]]:
    from google.genai import types

    search_response = await asyncio.to_thread(
        client.models.generate_content,
        model=_GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.1,
        ),
    )

    raw_text = (getattr(search_response, "text", "") or "").strip()
    grounded_urls: set[str] = set()
    try:
        metadata = search_response.candidates[0].grounding_metadata
        if metadata and metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if chunk.web and chunk.web.uri:
                    grounded_urls.add(chunk.web.uri)
    except (AttributeError, IndexError, TypeError):
        pass
    return raw_text, grounded_urls


async def collect_news_evidence(
    ticker: str,
    name: str,
    signal_inputs: list[Any],
    days_back: int = 7,
) -> list[dict[str, Any]]:
    """Return gemini_news monitoring candidates for the given ticker and signals."""
    if not settings.gemini_api_key or not signal_inputs:
        return []

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai SDK not installed — skipping news collection")
        return []

    signal_descriptors = _normalise_signal_search_inputs(signal_inputs)
    if not signal_descriptors:
        return []

    signals_text = _signal_search_bullets(signal_descriptors)

    now = datetime.now(timezone.utc)
    since_str = (now - timedelta(days=days_back)).strftime("%B %-d, %Y")
    until_str = now.strftime("%B %-d, %Y")

    broad_search_prompt = f"""\
Search for news articles published between {since_str} and {until_str} about {name} (ticker: {ticker}).

Find articles directly relevant to one or more of these investment signals:
{signals_text}

Only include articles where {name} or {ticker} is a primary subject.
Exclude broad stock roundups, market recaps, "why this stock is up/down today" explainers,
peer-comparison lists, or articles where the company is only mentioned in passing.

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
Discard anything outside the stated date range (__SINCE__ to __UNTIL__), unrelated to the signals,
or clearly a roundup / market-recap / "why the stock moved" explainer where the company is not the central subject.\
"""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        # Step 1 — run a broad company search plus a few focused signal searches.
        search_jobs: list[tuple[str, str | None]] = [(broad_search_prompt, None)]
        for signal_descriptor in _select_focused_signal_labels(signal_descriptors):
            signal_label = signal_descriptor["label"]
            search_jobs.append(
                (
                    _focused_signal_prompt(
                        ticker=ticker,
                        name=name,
                        signal=signal_descriptor,
                        since_str=since_str,
                        until_str=until_str,
                    ),
                    signal_label,
                )
            )

        grounded_urls: set[str] = set()
        raw_sections: list[str] = []
        last_error: Exception | None = None
        for prompt, signal_label in search_jobs:
            try:
                raw_text, search_grounded_urls = await _run_grounded_search(client, prompt=prompt)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Gemini grounded search failed for %s (%s): %s",
                    ticker,
                    signal_label or "broad",
                    exc,
                )
                continue
            if not raw_text or raw_text.lower().startswith("no news found"):
                continue
            grounded_urls.update(search_grounded_urls)
            section_header = f"SEARCH FOCUS: {signal_label}" if signal_label else "SEARCH FOCUS: broad company search"
            raw_sections.append(f"{section_header}\n{raw_text}")

        if not raw_sections:
            if last_error is not None:
                raise last_error
            return []

        # Step 2 — structured extraction, no search
        extraction_prompt = (
            extraction_prompt_template
            .replace("__NAME__", name)
            .replace("__TICKER__", ticker)
            .replace("__SINCE__", since_str)
            .replace("__UNTIL__", until_str)
            .replace("__SIGNALS__", signals_text)
            .replace("__RAW__", "\n\n".join(raw_sections))
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
        raise


def _to_candidates(
    items: list[dict],
    grounded_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    if grounded_urls is None:
        grounded_urls = set()

    candidates = []
    seen_article_keys: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = (item.get("headline") or "").strip()
        if not headline:
            continue
        url = item.get("url") or item.get("source_url") or ""
        summary = (item.get("summary") or "").strip()
        if _looks_like_roundup_noise(headline, summary):
            continue
        relevant_signals = item.get("relevant_signals")
        if not isinstance(relevant_signals, list):
            relevant_signals = []
        relevant_signals = [signal for signal in relevant_signals if isinstance(signal, str) and signal.strip()]
        if not relevant_signals:
            continue
        relevance = str(item.get("relevance", "medium")).lower().strip() or "medium"
        if relevance in _LOW_RELEVANCE_VALUES:
            continue
        matched_topics, topic_context = _topic_context_from_relevant_signals(relevant_signals)

        article_id = hashlib.sha256(f"{headline}{url}".encode()).hexdigest()[:16]
        dedupe_key = url.strip().lower() or article_id
        if dedupe_key in seen_article_keys:
            continue
        seen_article_keys.add(dedupe_key)

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
                "relevance": relevance,
                "source": "gemini_search",
                "is_grounded": bool(url and url in grounded_urls),
                "matched_topics": matched_topics,
                "topic_context": topic_context,
            },
        })
    return candidates
