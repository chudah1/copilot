import json
import logging
from typing import Any

import anthropic

from app.config import settings
from app.services.ai_utils import strip_code_fences

logger = logging.getLogger(__name__)

ALLOWED_INSIGHT_TYPES = {"event", "warning", "stable"}

DIGEST_PROMPT = """Write a weekly portfolio digest for a retail investor who tracks why they own each stock.
Use short bullet-style insights, not essay paragraphs.
Lead with the conclusion. Name the exact company, metric, customer, competitor, or event.
Name the exact change instead of writing "this suggests", "supports the thesis", "weakens the case", "the story", or "a pillar".
Use short sentences and familiar words. If a fact is uncertain, name the source of the uncertainty.

Portfolio holdings and their theses:
{holdings_section}

Events this week:
{events_section}

Stable holdings this week:
{stable_section}

Portfolio-level observations:
{observations_section}

Output ONLY valid JSON with this exact structure:
{{
    "insights": [
        {{
            "ticker": "AAPL",
            "type": "event" | "warning" | "stable",
            "headline": "Short headline (e.g. 'Earnings beat expectations')",
            "rationale": "One sentence: what happened and whether it matters to their reason for holding."
        }}
    ],
    "portfolio_warnings": [
        "A one-sentence warning about concentration or missing theses."
    ]
}}
"""


def _build_holdings_section(holdings_with_theses: list[dict[str, Any]]) -> str:
    lines = []
    for holding in holdings_with_theses:
        lines.append(
            (
                f"- {holding['ticker']} ({holding['name']}): Why own it: {holding.get('why_own_it', 'No thesis')}; "
                f"Must remain true: {holding.get('must_remain_true', 'Not specified')}; "
                f"What would change my mind: {holding.get('what_would_change_my_mind', 'Not specified')}"
            )
        )
    return "\n".join(lines)


def _build_events_section(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No events this week."
    return "\n".join(
        (
            f"- [{str(event.get('severity', 'info')).upper()}] "
            f"{event.get('ticker', 'UNKNOWN')}: "
            f"{event.get('title', 'Untitled event')} — "
            f"{event.get('summary', 'No summary available.')}"
        )
        for event in events
    )


def _build_stable_section(observations: dict[str, Any]) -> str:
    stable_holdings = observations.get("stable_holdings", [])
    if not stable_holdings:
        return "None."
    lines = []
    for stable in stable_holdings:
        stale_str = " (Stale thesis)" if stable.get("stale") else ""
        lines.append(f"- {stable['ticker']}{stale_str}")
    return "\n".join(lines)


def _build_observations_section(observations: dict[str, Any]) -> str:
    parts: list[str] = []
    if observations.get("concentration_warnings"):
        parts.append(f"Concentration: {observations['concentration_warnings']}")
    if observations.get("stale_theses"):
        parts.append(f"Stale theses (>90 days): {', '.join(observations['stale_theses'])}")
    if observations.get("missing_theses"):
        parts.append(f"Positions without theses: {', '.join(observations['missing_theses'])}")
    return "\n".join(parts) if parts else "None."


def _build_digest_prompt(
    holdings_with_theses: list[dict[str, Any]],
    events: list[dict[str, Any]],
    observations: dict[str, Any],
) -> str:
    return DIGEST_PROMPT.format(
        holdings_section=_build_holdings_section(holdings_with_theses),
        events_section=_build_events_section(events),
        stable_section=_build_stable_section(observations),
        observations_section=_build_observations_section(observations),
    )


def _parse_digest_response(text: str) -> dict[str, Any]:
    payload = json.loads(strip_code_fences(text))
    insights = payload.get("insights")
    portfolio_warnings = payload.get("portfolio_warnings")

    if not isinstance(insights, list):
        raise ValueError("Digest insights must be a list.")
    if not isinstance(portfolio_warnings, list) or any(not isinstance(item, str) for item in portfolio_warnings):
        raise ValueError("Digest portfolio_warnings must be a list of strings.")

    normalized_insights: list[dict[str, str]] = []
    for insight in insights:
        if not isinstance(insight, dict):
            raise ValueError("Each digest insight must be an object.")
        ticker = insight.get("ticker")
        insight_type = insight.get("type")
        headline = insight.get("headline")
        rationale = insight.get("rationale")
        if not all(isinstance(field, str) and field.strip() for field in (ticker, insight_type, headline, rationale)):
            raise ValueError("Each digest insight must include non-empty string fields.")
        if insight_type not in ALLOWED_INSIGHT_TYPES:
            raise ValueError(f"Unsupported digest insight type: {insight_type}")
        normalized_insights.append(
            {
                "ticker": ticker,
                "type": insight_type,
                "headline": headline,
                "rationale": rationale,
            }
        )

    return {
        "insights": normalized_insights,
        "portfolio_warnings": portfolio_warnings,
    }


async def _call_anthropic_digest(prompt: str) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        timeout=30.0,
    )
    return _parse_digest_response(response.content[0].text)


def _fallback_digest(
    holdings_with_theses: list[dict[str, Any]],
    events: list[dict[str, Any]],
    observations: dict[str, Any],
) -> dict[str, Any]:
    insights: list[dict[str, str]] = []

    for event in events:
        insights.append(
            {
                "ticker": event["ticker"],
                "type": "event",
                "headline": event["title"],
                "rationale": event["summary"],
            }
        )

    for stable in observations.get("stable_holdings", []):
        if stable.get("stale"):
            insights.append(
                {
                    "ticker": stable["ticker"],
                    "type": "warning",
                    "headline": "Thesis is getting stale",
                    "rationale": "It's been a while since you updated your reasoning for holding this.",
                }
            )
        else:
            insights.append(
                {
                    "ticker": stable["ticker"],
                    "type": "stable",
                    "headline": "Nothing meaningful this week",
                    "rationale": "No material company news or monitored changes were found.",
                }
            )

    warnings: list[str] = []
    if observations.get("concentration_warnings"):
        warnings.append(observations["concentration_warnings"])
    if observations.get("stale_theses"):
        warnings.append(f"Stale theses (>90 days): {', '.join(observations['stale_theses'])}")
    if observations.get("missing_theses"):
        warnings.append(f"Positions without an active thesis: {', '.join(observations['missing_theses'])}")

    return {
        "insights": insights,
        "portfolio_warnings": warnings,
    }


async def generate_digest_content(
    holdings_with_theses: list[dict[str, Any]],
    events: list[dict[str, Any]],
    observations: dict[str, Any],
) -> dict[str, Any] | None:
    prompt = _build_digest_prompt(holdings_with_theses, events, observations)

    try:
        if not settings.anthropic_api_key:
            return _fallback_digest(holdings_with_theses, events, observations)
        return await _call_anthropic_digest(prompt)
    except Exception as exc:
        logger.error("Digest generation failed: %s", exc)
        return _fallback_digest(holdings_with_theses, events, observations)
