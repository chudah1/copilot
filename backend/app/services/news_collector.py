"""Gemini Flash news collector.

Uses Gemini 2.0 Flash with Google Search grounding to find recent news
relevant to specific thesis signals. Falls back to empty list on any error
so it never blocks the monitoring pipeline.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

MAX_SIGNALS = 6  # avoid overly long prompts
_GEMINI_MODEL = "gemini-2.5-flash"

_PROMPT_TEMPLATE = """\
Search for news published in the last 7 days about {name} (ticker: {ticker}).

Investment signals to monitor:
{signals_text}

Find articles directly relevant to one or more signals above. Return ONLY a JSON array:
[
  {{
    "headline": "article headline",
    "url": "article url",
    "date": "YYYY-MM-DD",
    "summary": "1-2 sentence summary of what happened",
    "relevant_signals": ["matching signal label from the list above"],
    "relevance": "high"
  }}
]

Rules:
- Only include articles from the last 7 days
- Only include articles relevant to at least one listed signal
- Return [] if nothing relevant found
- Return only the JSON array, no other text\
"""


async def collect_news_evidence(
    ticker: str,
    name: str,
    signal_labels: list[str],
) -> list[dict[str, Any]]:
    """Return gemini_news monitoring candidates for the given ticker and signals.

    Silently returns [] if Gemini is unconfigured, quota is exceeded, or any
    other failure occurs — news collection is enrichment, not critical path.
    """
    if not settings.gemini_api_key or not signal_labels:
        return []

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai SDK not installed — skipping news collection")
        return []

    signals_text = "\n".join(f"- {label}" for label in signal_labels[:MAX_SIGNALS])
    prompt = _PROMPT_TEMPLATE.format(ticker=ticker, name=name, signals_text=signals_text)

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0,
            ),
        )
        text = getattr(response, "text", "") or ""
        items = _parse_json_array(text)
        return _to_candidates(items)
    except Exception as exc:
        logger.warning("Gemini news collection failed for %s: %s", ticker, exc)
        return []


def _parse_json_array(text: str) -> list[dict]:
    """Extract a JSON array from an LLM response, handling markdown wrappers."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    # Last resort: find the first [...] block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return []


def _to_candidates(items: list[dict]) -> list[dict[str, Any]]:
    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = (item.get("headline") or "").strip()
        if not headline:
            continue
        url = item.get("url") or item.get("source_url")
        summary = (item.get("summary") or "").strip()
        relevant_signals = item.get("relevant_signals")
        if not isinstance(relevant_signals, list):
            relevant_signals = []

        # Stable dedup ID: hash of headline + url
        article_id = hashlib.sha256(f"{headline}{url or ''}".encode()).hexdigest()[:16]

        candidates.append({
            "event_type": "gemini_news",
            "description": f"{headline} — {summary}" if summary else headline,
            "evidence": {
                "article_id": article_id,
                "headline": headline,
                "summary": summary,
                "url": url,
                "date": item.get("date"),
                "relevant_signals": relevant_signals,
                "relevance": item.get("relevance", "medium"),
                "source": "gemini_search",
            },
        })
    return candidates
