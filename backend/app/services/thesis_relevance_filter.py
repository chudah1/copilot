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
  - If no → drop, capturing a short reason the digest can quote so the user
    can see the filter is doing thoughtful work instead of just deleting
    things — quiet products only feel quiet-and-informed if the reviewed-
    but-dropped items are visible.

The check is intentionally cheap (gpt-4o-mini) because it's a binary
relevance decision, not severity classification. Severity stays on gpt-4o
in ai_monitor.classify_event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DroppedCandidate:
    """A news-style candidate the LLM ruled out, plus the sentence it wrote
    to explain the drop. The digest builder samples these to render the
    'we reviewed these and didn't fire an alert' block."""
    headline: str
    source: str
    published_at: str | None
    url: str | None
    reason: str
    ticker: str
    matched_signal_labels: list[str]

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

When relevant is false, also return `reason`: one plain sentence, addressed to the investor, that names what the article is about AND what thesis dimension it doesn't touch. Example: "The downgrade is about near-term China revenue exposure, which doesn't touch your CUDA software moat pillar." Do not mention filter mechanics, models, or scores. Keep it under 30 words.

Return a single JSON object: {{"relevant": true|false, "matched_signals": ["label1", "label2"], "reason": "<sentence when relevant is false, empty string otherwise>"}}.
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
) -> tuple[bool, list[str], str]:
    """Ask the LLM whether one candidate touches any thesis signal. Returns
    (relevant, matched_signals, drop_reason). drop_reason is only meaningful
    when relevant=False; empty string otherwise."""
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
        # Enough budget for the extra `reason` string (up to ~30 words) plus
        # the boolean + signal-label array.
        max_tokens=220,
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
        return True, [], ""
    relevant = bool(parsed.get("relevant"))
    matched_signals = parsed.get("matched_signals")
    if not isinstance(matched_signals, list):
        matched_signals = []
    matched_signals = [str(s).strip() for s in matched_signals if str(s).strip()]
    reason_raw = parsed.get("reason")
    drop_reason = str(reason_raw).strip() if isinstance(reason_raw, str) else ""
    return relevant, matched_signals, drop_reason


def _extract_dropped_metadata(
    candidate: dict[str, Any], *, ticker: str, reason: str
) -> DroppedCandidate:
    """Package a dropped candidate into the shape the digest / API consumes."""
    evidence = candidate.get("evidence") or {}
    headline = (evidence.get("headline") or candidate.get("description") or "").strip()
    matched = evidence.get("relevant_signals") or evidence.get("matched_signal_labels") or []
    if not isinstance(matched, list):
        matched = []
    matched_clean = [str(x).strip() for x in matched if str(x).strip()]
    published_at = evidence.get("published_at")
    if published_at is not None and not isinstance(published_at, str):
        # coverage_pass.payload is JSON so datetimes need serialising here
        try:
            published_at = published_at.isoformat()
        except AttributeError:
            published_at = str(published_at)
    return DroppedCandidate(
        headline=headline[:200],
        source=str(candidate.get("event_type") or "unknown"),
        published_at=published_at if isinstance(published_at, str) else None,
        url=evidence.get("url") if isinstance(evidence.get("url"), str) else None,
        reason=reason.strip()[:300],
        ticker=ticker,
        matched_signal_labels=matched_clean[:3],
    )


async def filter_candidates_by_thesis_relevance_with_drops(
    candidates: list[dict[str, Any]],
    *,
    signal_descriptors: list[dict[str, str]],
    ticker: str,
    why_own_it: str,
) -> tuple[list[dict[str, Any]], list[DroppedCandidate]]:
    """Same as filter_candidates_by_thesis_relevance but also returns the
    dropped items with per-item reasons — powers the digest's 'we reviewed
    these and didn't fire an alert' section.

    Return shape: (kept_candidates, dropped_items). Dropped items only include
    candidates the LLM explicitly ruled out; parse errors and gather()
    exceptions default to keep and don't populate a drop, since we can't
    honestly explain those to the user.
    """
    if not candidates or not signal_descriptors or not settings.openai_api_key:
        return candidates, []

    targets_idx = [
        i for i, c in enumerate(candidates)
        if c.get("event_type") in _RELEVANCE_FILTER_EVENT_TYPES
    ]
    if not targets_idx:
        return candidates, []

    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.warning("OpenAI SDK not installed — skipping thesis-relevance filter")
        return candidates, []

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
    dropped_items: list[DroppedCandidate] = []
    for idx, judgment in zip(targets_idx, judgments):
        if isinstance(judgment, BaseException):
            logger.warning("Relevance filter errored on candidate %d: %s", idx, judgment)
            # Default to keep on error — same safer-than-silent-drop policy.
            continue
        relevant, matched_signals, drop_reason = judgment
        if not relevant:
            dropped_idx.add(idx)
            if drop_reason:
                dropped_items.append(
                    _extract_dropped_metadata(
                        candidates[idx], ticker=ticker, reason=drop_reason
                    )
                )
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

    kept = [c for i, c in enumerate(candidates) if i not in dropped_idx]
    return kept, dropped_items


async def filter_candidates_by_thesis_relevance(
    candidates: list[dict[str, Any]],
    *,
    signal_descriptors: list[dict[str, str]],
    ticker: str,
    why_own_it: str,
) -> list[dict[str, Any]]:
    """Back-compat wrapper — call the _with_drops variant when you also need
    the per-item drop reasons for the digest 'reviewed this week' surface."""
    kept, _ = await filter_candidates_by_thesis_relevance_with_drops(
        candidates,
        signal_descriptors=signal_descriptors,
        ticker=ticker,
        why_own_it=why_own_it,
    )
    return kept
