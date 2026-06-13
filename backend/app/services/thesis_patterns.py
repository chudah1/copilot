import re
from dataclasses import dataclass
from typing import Any, Callable


def contains_keyword(text: str, kw: str) -> bool:
    kw = kw.lower().strip()
    if " " in kw or "-" in kw:
        return kw in text
    return re.search(rf"\b{re.escape(kw)}\b", text) is not None


@dataclass(frozen=True)
class QualitativeWatchPattern:
    id: str
    matches: Callable[[str], bool]
    build: Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class StoryMetricPattern:
    metric: str
    rationale: str
    trigger_keywords: tuple[str, ...]
    include_story_growth_only: bool = False


def _extract_restricted_thing(text: str) -> str:
    restricted_thing = "the thesis-critical product or channel"
    match = re.search(
        r"(?:fda|regulator(?:y)?)\s+(?:formally\s+)?(?:ban(?:s|ned)?|restrict(?:s|ed)?|pull(?:s|ed)?|block(?:s|ed)?)\s+([^,.]+?)(?:\s+and\b|[,.]|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip(" -")
        if candidate:
            restricted_thing = candidate
    return restricted_thing


def _extract_affected_economics(text: str) -> str:
    affected_economics = "the thesis-critical unit economics"
    match = re.search(
        r"(?:changes?\s+to|forces?)\s+([^,.]+?\s+economics)(?:\s+without\b|[,.]|$)",
        text,
        re.IGNORECASE,
    )
    if match:
        candidate = match.group(1).strip(" -")
        if candidate:
            affected_economics = candidate
    return affected_economics


def _extract_deal_name(text: str) -> str:
    deal_name = "the acquisition or integration"
    match = re.search(
        r"\b([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+)*)\s+(?:deal|acquisition)\b",
        text,
    )
    if match:
        candidate = match.group(1).strip(" -")
        if candidate:
            deal_name = candidate
    return deal_name


def _matches_glp1_regulatory(text: str) -> bool:
    return (
        any(contains_keyword(text, kw) for kw in ("glp-1", "semaglutide", "compounded"))
        and any(contains_keyword(text, kw) for kw in ("fda", "ban", "restrict", "pull"))
    )


def _matches_regulatory_economics(text: str) -> bool:
    generic_regulatory_context = any(
        contains_keyword(text, kw)
        for kw in ("regulatory", "regulation", "regulator", "fee cut", "fee cuts", "economics", "app store", "open up")
    )
    replacement_context = any(
        contains_keyword(text, kw)
        for kw in (
            "replacement path",
            "replacement monetization path",
            "mitigation path",
            "replacement",
            "mitigation",
            "offset",
            "monetization path",
        )
    )
    return generic_regulatory_context and replacement_context


def _matches_funding_pressure(text: str) -> bool:
    funding_context = any(
        contains_keyword(text, kw)
        for kw in (
            "funding cost",
            "funding costs",
            "funding model",
            "funding capacity",
            "warehouse line",
            "capital markets",
            "securitization",
        )
    )
    return funding_context and any(contains_keyword(text, kw) for kw in ("spike", "offset", "available", "capacity"))


def _matches_credit_break(text: str) -> bool:
    return any(
        contains_keyword(text, kw)
        for kw in ("delinquency", "delinquencies", "underwriting", "credit deterioration", "credit quality", "charge-off")
    )


def _matches_merchant_repeat(text: str) -> bool:
    merchant_repeat_context = any(
        contains_keyword(text, kw)
        for kw in ("merchant growth", "merchant adoption", "repeat user", "repeat usage", "gross merchandise volume", "gmv")
    )
    return merchant_repeat_context and any(contains_keyword(text, kw) for kw in ("stall", "weakens", "compounding", "growth"))


def _matches_integration_drag(text: str) -> bool:
    return any(contains_keyword(text, kw) for kw in ("eucalyptus", "acquisition", "deal", "integration", "overhead drag"))


QUALITATIVE_WATCH_PATTERNS: tuple[QualitativeWatchPattern, ...] = (
    QualitativeWatchPattern(
        id="glp1_regulatory_replacement",
        matches=_matches_glp1_regulatory,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": f"a regulatory restriction hits {_extract_restricted_thing(text)} and management fails to present a credible replacement or mitigation path by next earnings",
            "direction": "threatens",
            "rationale": "If the core product or channel is restricted and management cannot pivot quickly, the main growth driver is impaired.",
        },
    ),
    QualitativeWatchPattern(
        id="regulatory_economics_replacement",
        matches=_matches_regulatory_economics,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": f"a regulatory change forces meaningful changes to {_extract_affected_economics(text)} and management has no credible replacement or mitigation path",
            "direction": "threatens",
            "rationale": "If regulation changes the core economics and management cannot offset it, the thesis weakens materially.",
        },
    ),
    QualitativeWatchPattern(
        id="funding_pressure",
        matches=_matches_funding_pressure,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": "funding costs spike or funding capacity tightens and management cannot offset it",
            "direction": "threatens",
            "rationale": "If funding becomes materially more expensive or scarce, growth can break even before demand does.",
        },
    ),
    QualitativeWatchPattern(
        id="credit_break",
        matches=_matches_credit_break,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": "delinquencies rise enough to show underwriting is breaking",
            "direction": "threatens",
            "rationale": "If credit quality deteriorates enough to expose underwriting weakness, the thesis breaks.",
        },
    ),
    QualitativeWatchPattern(
        id="merchant_repeat_usage",
        matches=_matches_merchant_repeat,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": "merchant growth stalls and repeat usage weakens materially",
            "direction": "threatens",
            "rationale": "If merchant expansion and repeat usage both weaken, the demand engine behind volume growth is fading.",
        },
    ),
    QualitativeWatchPattern(
        id="integration_overhead_drag",
        matches=_matches_integration_drag,
        build=lambda text: {
            "kind": "news_watch",
            "watch_for": f"{_extract_deal_name(text)} fails to add a clear new revenue line and starts reading like overhead drag",
            "direction": "threatens",
            "rationale": "If the deal adds cost without new revenue traction, the expansion case weakens.",
        },
    ),
)


STORY_METRIC_PATTERNS: tuple[StoryMetricPattern, ...] = (
    StoryMetricPattern(
        metric="revenue_growth_yoy",
        rationale="Revenue growth must stay positive to validate this thesis.",
        trigger_keywords=("revenue", "sales", "orders", "bookings", "subscribers", "users", "capex", "top line", "top-line"),
    ),
    StoryMetricPattern(
        metric="revenue_growth_yoy",
        rationale="Revenue growth must stay positive to validate this thesis.",
        trigger_keywords=("growth", "demand", "adoption", "ai"),
        include_story_growth_only=True,
    ),
    StoryMetricPattern(
        metric="earnings_growth_yoy",
        rationale="The thesis depends on profitable execution; monitor earnings growth.",
        trigger_keywords=("margin", "margins", "profit", "profitability", "earnings", "cash flow", "ebitda", "eps"),
    ),
)


def infer_qualitative_watch_hints(text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    hints: list[dict[str, Any]] = []
    for pattern in QUALITATIVE_WATCH_PATTERNS:
        if pattern.matches(lowered):
            hints.append(pattern.build(text))
    return hints


def infer_story_watch_hints(text: str, *, include_story_growth: bool = False) -> list[dict[str, Any]]:
    lowered = text.lower()
    watch_hints: list[dict[str, Any]] = infer_qualitative_watch_hints(text)

    for pattern in STORY_METRIC_PATTERNS:
        if pattern.include_story_growth_only and not include_story_growth:
            continue
        if any(contains_keyword(lowered, kw) for kw in pattern.trigger_keywords):
            watch_hints.append(
                {
                    "kind": "metric_threshold",
                    "metric": pattern.metric,
                    "operator": ">=",
                    "threshold": 0.0,
                    "rationale": pattern.rationale,
                }
            )

    if len(watch_hints) < 3:
        watch_hints.append(
            {
                "kind": "price_move_pct",
                "threshold": 5.0,
                "rationale": "Prompt a review when price moves sharply.",
            }
        )

    return watch_hints
