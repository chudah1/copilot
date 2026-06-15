"""LLM-based thesis-aware relevance filter for news-style candidates.

The walkthrough on 2026-06-15 found that when Gemini is down, the yfinance/
Alpha Vantage news candidates that survive the topic/keyword filter are
mostly noise (13F filings, fund-flow announcements, ETF rebalancing). They
all match qualitative keywords but don't actually test the user's thesis.
The downstream classifier then routes them to `info` per the "same-company
news" default rule, polluting the user's notifications.

This module runs a quick LLM relevance check on each news-style candidate
*before* classification:
  - "Does this content directly touch any of the user's stated thesis
    signals?"
  - If yes → keep, tag with matched signal labels for the classifier.
  - If no → drop.

The check is intentionally cheap (gpt-4o-mini) because it's a binary
relevance decision, not severity classification. Severity stays on gpt-4o
in ai_monitor.classify_event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# Only news-style candidates need this filter — quantitative events
# (price_move, metric_breach, watch_hint_breach, earnings_surprise, etc.)
# are already grounded in stated thresholds.
_RELEVANCE_FILTER_EVENT_TYPES = {
    "news_or_earnings_candidate",
    "product_ramp_update",
    "news_keyword_match",
    "contract_renewal_update",
    "funding_condition_update",
    "margin_pressure_update",
    "customer_capex_signal",
    "gemini_news",
}

_RELEVANCE_MODEL = "gpt-4o-mini"

_RELEVANCE_PROMPT = """You are filtering news for a stock investor.

The investor wrote this thesis for owning {ticker}:
- Why they own it: {why_own_it}
- Stated watch signals (any of these matter to them):
{signal_list}

A news item arrived:
"{headline}: {summary}"

Decide: does this news touch any of the stated watch signals, even peripherally?

- YES if the news is about the holding company AND mentions something that touches a signal — a product, segment, regulator, competitor, metric, or theme the signals reference.
- NO if the news is about institutional fund holdings (13F filings, fund rebalancing, ETF flow updates), generic market commentary, or unrelated corporate activity that doesn't touch any signal.

Return a single JSON object: {{"relevant": true|false, "matched_signals": ["label1", "label2"]}}.
Empty array if not relevant. No prose, no markdown."""


def _format_signal_list(signal_descriptors: list[dict[str, str]]) -> str:
    if not signal_descriptors:
        return "  (no signals)"
    lines = []
    for s in signal_descriptors:
        label = (s.get("label") or "").strip()
        claim = (s.get("claim_text") or "").strip()
        if claim:
            lines.append(f"  - {label} (from claim: {claim[:120]})")
        else:
            lines.append(f"  - {label}")
    return "\n".join(lines)


async def _judge_one(
    client: Any,
    candidate: dict[str, Any],
    *,
    ticker: str,
    why_own_it: str,
    signal_list_text: str,
) -> tuple[bool, list[str]]:
    """Ask the LLM whether one candidate touches any thesis signal."""
    evidence = candidate.get("evidence") or {}
    headline = (evidence.get("headline") or candidate.get("description") or "").strip()
    summary = (evidence.get("summary") or "").strip()

    prompt = _RELEVANCE_PROMPT.format(
        ticker=ticker,
        why_own_it=why_own_it.strip(),
        signal_list=signal_list_text,
        headline=headline[:300],
        summary=summary[:500],
    )

    response = await client.chat.completions.create(
        model=_RELEVANCE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=128,
        response_format={"type": "json_object"},
        timeout=15.0,
    )
    raw = (response.choices[0].message.content or "{}").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Default to keep on parse failure — safer than silently dropping
        # potentially-relevant news because the model produced bad JSON.
        logger.warning("Relevance filter parse error for '%s': %r", headline[:80], raw[:120])
        return True, []
    relevant = bool(parsed.get("relevant"))
    matched_signals = parsed.get("matched_signals")
    if not isinstance(matched_signals, list):
        matched_signals = []
    matched_signals = [str(s).strip() for s in matched_signals if str(s).strip()]
    return relevant, matched_signals


async def filter_candidates_by_thesis_relevance(
    candidates: list[dict[str, Any]],
    *,
    signal_descriptors: list[dict[str, str]],
    ticker: str,
    why_own_it: str,
) -> list[dict[str, Any]]:
    """Drop news-style candidates that don't touch any thesis signal.

    If signal_descriptors is empty (no decomposition yet, or no signals
    extracted), the filter is a no-op — we'd have no basis to judge
    relevance, and silently dropping news during onboarding would erase the
    first-pulse experience entirely.
    """
    if not candidates or not signal_descriptors or not settings.openai_api_key:
        return candidates

    targets_idx = [
        i for i, c in enumerate(candidates)
        if c.get("event_type") in _RELEVANCE_FILTER_EVENT_TYPES
    ]
    if not targets_idx:
        return candidates

    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("OpenAI SDK not installed — skipping thesis-relevance filter")
        return candidates

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    signal_list_text = _format_signal_list(signal_descriptors)

    judgments = await asyncio.gather(
        *(
            _judge_one(
                client,
                candidates[i],
                ticker=ticker,
                why_own_it=why_own_it,
                signal_list_text=signal_list_text,
            )
            for i in targets_idx
        ),
        return_exceptions=True,
    )

    dropped_idx: set[int] = set()
    for idx, judgment in zip(targets_idx, judgments):
        if isinstance(judgment, BaseException):
            logger.warning("Relevance filter errored on candidate %d: %s", idx, judgment)
            # Default to keep on error — same safer-than-silent-drop policy.
            continue
        relevant, matched_signals = judgment
        if not relevant:
            dropped_idx.add(idx)
            continue
        # Tag the candidate with the LLM's matched-signal hints so downstream
        # signal binding can use them if it didn't already (the existing
        # match_candidates_to_signals path checks evidence.relevant_signals).
        if matched_signals:
            evidence = candidates[idx].setdefault("evidence", {})
            existing = evidence.get("relevant_signals")
            if isinstance(existing, list):
                merged = list(dict.fromkeys(existing + matched_signals))
            else:
                merged = matched_signals
            evidence["relevant_signals"] = merged

    if dropped_idx:
        logger.info(
            "Thesis-relevance filter dropped %d of %d news candidates for %s",
            len(dropped_idx),
            len(targets_idx),
            ticker,
        )

    return [c for i, c in enumerate(candidates) if i not in dropped_idx]
