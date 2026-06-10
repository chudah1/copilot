from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache: {ticker:YYYY-MM-DD:draft_fingerprint} → StressTestResult.
# Keyed by the draft thesis too, so the grounding path (which always supplies a
# draft) dedupes its paid LLM call instead of missing every time. The output is
# a pure function of ticker + draft, so identical input is safe to share across
# callers; the live price is always re-applied and never served from cache.
# Process-local — does not synchronise across uvicorn workers. Replace with Redis for multi-worker deployments.
_cache: dict[str, StressTestResult] = {}


# Signal types the monitoring pipeline can actually watch. The numeric ones map
# to a watch_hint checked against the market feed; "news_watch" is qualitative —
# a natural-language condition the classifier evaluates against news/filings.
NUMERIC_CANDIDATE_SIGNAL_TYPES = ("price_move", "revenue_growth", "earnings_growth")
CANDIDATE_SIGNAL_TYPES = NUMERIC_CANDIDATE_SIGNAL_TYPES + ("news_watch",)

RISK_CATEGORY_ORDER = [
    "Business risk",
    "Competitive risk",
    "Financial risk",
    "Macro risk",
    "Management risk",
]
RISK_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Competitive risk": (
        "compet", "market share", "pricing power", "substitute", "customer loss", "defection",
    ),
    "Financial risk": (
        "valuation", "multiple", "margin", "cash", "debt", "balance sheet", "dilution", "profit",
        "revenue", "earnings", "free cash flow", "fcf",
    ),
    "Macro risk": (
        "macro", "rate", "inflation", "recession", "tariff", "china", "regulation", "cyclical", "demand shock",
        "fx", "currency", "geopolit",
    ),
    "Management risk": (
        "management", "ceo", "cfo", "leadership", "capital allocation", "execution", "guidance", "insider",
    ),
    "Business risk": (
        "business model", "product", "adoption", "capacity", "supply", "execution", "concentration", "customer",
    ),
}


@dataclass
class CandidateSignal:
    """A structured, confirmable watch the stress-test proposes — the bridge from
    a vague thesis to a monitorable signal.

    Numeric watches (price_move / revenue_growth / earnings_growth) use
    threshold_pct (a human percentage, e.g. 8.0) + operator. Qualitative watches
    (news_watch) use watch_for (a natural-language condition) + direction, and
    are evaluated by the AI against incoming news rather than a number."""

    signal_type: str          # one of CANDIDATE_SIGNAL_TYPES
    label: str                # human-readable, e.g. "Revenue growth stays above 8%"
    threshold_pct: float = 0.0  # percentage (numeric watches only)
    rationale: str = ""
    operator: str | None = None  # ">=" / "<=" for metric thresholds; None otherwise
    watch_for: str | None = None  # news_watch: the condition to watch for
    direction: str | None = None  # news_watch: "threatens" | "supports"


@dataclass
class StressTestRiskGroup:
    category: str
    items: list[str]


@dataclass
class StressTestSourceNote:
    label: str
    detail: str
    source: str
    url: str | None = None


@dataclass
class StressTestOutput:
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    what_to_watch: list[str]
    risk_groups: list[StressTestRiskGroup] = field(default_factory=list)
    source_notes: list[StressTestSourceNote] = field(default_factory=list)
    candidate_signals: list[CandidateSignal] = field(default_factory=list)


@dataclass
class StressTestResult:
    ticker: str
    bear_case: str
    key_risks: list[str]
    blind_spots: list[str]
    what_to_watch: list[str]
    current_price: float | None
    cached: bool = False
    risk_groups: list[StressTestRiskGroup] = field(default_factory=list)
    source_notes: list[StressTestSourceNote] = field(default_factory=list)
    candidate_signals: list[CandidateSignal] = field(default_factory=list)


async def _generate(
    ticker: str,
    draft_thesis: str | None,
    company_data: Any,
) -> StressTestOutput:
    from app.services.ai_thesis import generate_stress_test_analysis

    return await generate_stress_test_analysis(
        ticker=ticker,
        draft_thesis=draft_thesis,
        company_data=company_data,
        current_price=company_data.current_price if company_data else None,
    )


async def run_stress_test(
    ticker: str,
    draft_thesis: str | None,
    company_data: Any = None,
) -> StressTestResult:
    ticker = ticker.upper()
    current_price = company_data.current_price if company_data else None
    draft_fingerprint = hashlib.sha256((draft_thesis or "").encode("utf-8")).hexdigest()[:16]
    cache_key = f"{ticker}:{datetime.now(timezone.utc).date().isoformat()}:{draft_fingerprint}"

    cached = _cache.get(cache_key)
    if cached is not None:
        return StressTestResult(
            ticker=cached.ticker,
            bear_case=cached.bear_case,
            key_risks=cached.key_risks,
            blind_spots=cached.blind_spots,
            what_to_watch=cached.what_to_watch,
            current_price=current_price,  # always use live price, not cached
            cached=True,
            risk_groups=getattr(cached, "risk_groups", None) or _derive_risk_groups(cached.key_risks),
            source_notes=getattr(cached, "source_notes", None) or _build_source_notes(company_data, current_price),
            candidate_signals=cached.candidate_signals,
        )

    output = await _generate(
        ticker=ticker,
        draft_thesis=draft_thesis,
        company_data=company_data,
    )

    result = StressTestResult(
        ticker=ticker,
        bear_case=output.bear_case,
        key_risks=output.key_risks,
        blind_spots=output.blind_spots,
        what_to_watch=output.what_to_watch,
        current_price=current_price,
        cached=False,
        risk_groups=output.risk_groups or _derive_risk_groups(output.key_risks),
        source_notes=output.source_notes or _build_source_notes(company_data, current_price),
        candidate_signals=output.candidate_signals,
    )

    _cache[cache_key] = result
    return result


def _derive_risk_groups(key_risks: list[str]) -> list[StressTestRiskGroup]:
    if not key_risks:
        return []

    grouped: dict[str, list[str]] = {category: [] for category in RISK_CATEGORY_ORDER}
    for risk in key_risks:
        category = _categorize_risk(risk)
        grouped.setdefault(category, []).append(risk)

    return [
        StressTestRiskGroup(category=category, items=items)
        for category in RISK_CATEGORY_ORDER
        for items in [grouped.get(category, [])]
        if items
    ]


def _categorize_risk(risk: str) -> str:
    lowered = risk.lower()
    for category in RISK_CATEGORY_ORDER:
        if any(keyword in lowered for keyword in RISK_CATEGORY_KEYWORDS[category]):
            return category
    return "Business risk"


def _build_source_notes(
    company_data: Any,
    current_price: float | None,
) -> list[StressTestSourceNote]:
    notes: list[StressTestSourceNote] = []

    price = getattr(company_data, "current_price", None) if company_data is not None else current_price
    if price is not None:
        notes.append(
            StressTestSourceNote(
                label="Price",
                detail=f"Current price {price:.2f}",
                source="Market quote",
            )
        )

    if company_data is None:
        return notes

    pe_ratio = _safe_float(getattr(company_data, "pe_ratio", None))
    if pe_ratio is not None:
        notes.append(
            StressTestSourceNote(
                label="Valuation",
                detail=f"P/E ratio {pe_ratio:.1f}x",
                source="Company overview",
            )
        )

    revenue_growth = _safe_float(getattr(company_data, "revenue_growth_yoy", None))
    if revenue_growth is not None:
        notes.append(
            StressTestSourceNote(
                label="Revenue growth",
                detail=f"Revenue growth {revenue_growth * 100:+.1f}% YoY",
                source="Company overview",
            )
        )

    earnings_growth = _safe_float(getattr(company_data, "earnings_growth_yoy", None))
    if earnings_growth is not None:
        notes.append(
            StressTestSourceNote(
                label="Earnings growth",
                detail=f"Earnings growth {earnings_growth * 100:+.1f}% YoY",
                source="Company overview",
            )
        )

    surprise = _safe_float(getattr(company_data, "recent_earnings_surprise_pct", None))
    if surprise is not None:
        notes.append(
            StressTestSourceNote(
                label="Recent earnings",
                detail=f"Earnings surprise {surprise:+.1f}%",
                source="Quarterly earnings feed",
            )
        )

    if getattr(company_data, "news_items", None):
        for item in company_data.news_items[:2]:
            headline = getattr(item, "headline", None)
            if not headline:
                continue
            notes.append(
                StressTestSourceNote(
                    label="Recent news",
                    detail=headline,
                    source=getattr(item, "source", None) or "News feed",
                    url=getattr(item, "url", None),
                )
            )

    ec = getattr(company_data, "earnings_call", None)
    transcript_cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    if ec and getattr(ec, "highlights", None) and getattr(ec, "call_date", None) and ec.call_date >= transcript_cutoff:
        highlight = next((h for h in ec.highlights if h), None)
        if highlight:
            notes.append(
                StressTestSourceNote(
                    label="Earnings call",
                    detail=highlight,
                    source="Transcript highlights",
                )
            )

    return notes[:6]


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
