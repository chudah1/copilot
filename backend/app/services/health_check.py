import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.ai_monitor import classify_event
from app.services.market_data import CompanyData, fetch_company_data
from app.services.monitoring import (
    RuleCheckResult,
    check_metric_watch_hints,
    generate_monitoring_candidates,
)

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedCandidate:
    event_type: str
    description: str
    severity: str | None = None
    ai_analysis: str | None = None


@dataclass
class HealthCheckResult:
    ticker: str
    current_price: float | None = None
    sector: str | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    upcoming_earnings_date: datetime | None = None
    recent_earnings_surprise_pct: float | None = None
    candidates: list[ClassifiedCandidate] = field(default_factory=list)
    watch_hints_status: list[RuleCheckResult] = field(default_factory=list)
    recent_news_count: int = 0
    thesis_assessment: str = "all_clear"
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _assess(candidates: list[ClassifiedCandidate]) -> str:
    """Derive overall assessment from classified candidates."""
    severities = {c.severity for c in candidates if c.severity}
    if "thesis_breaking" in severities:
        return "review_needed"
    if "warning" in severities:
        return "watch"
    if candidates:
        return "watch"
    return "all_clear"


def _market_values(company_data: CompanyData) -> dict[str, float]:
    market_values = {
        "revenue_growth_yoy": company_data.revenue_growth_yoy,
        "earnings_growth_yoy": company_data.earnings_growth_yoy,
        "pe_ratio": company_data.pe_ratio,
        "dividend_yield": company_data.dividend_yield,
    }
    return {key: value for key, value in market_values.items() if value is not None}


async def _classify_candidates(
    thesis: Thesis,
    raw_candidates: list[dict],
    ticker: str | None = None,
    company_name: str | None = None,
) -> list[ClassifiedCandidate]:
    classified: list[ClassifiedCandidate] = []
    for candidate in raw_candidates:
        description = candidate.get("description", "")

        try:
            result = await classify_event(
                why_own_it=thesis.why_own_it,
                must_remain_true=thesis.must_remain_true,
                what_would_change_my_mind=thesis.what_would_change_my_mind,
                ai_summary=thesis.ai_summary,
                event_description=description,
                ticker=ticker,
                company_name=company_name,
            )
        except Exception:
            logger.exception("Health check classification failed for thesis %s", thesis.id)
            result = None

        if result is None:
            continue

        classified.append(
            ClassifiedCandidate(
                event_type=candidate.get("event_type", "unknown"),
                description=description,
                severity=result.severity,
                ai_analysis=result.analysis,
            )
        )
    return classified


async def run_health_check(thesis: Thesis, holding: Holding) -> HealthCheckResult:
    """Run a stateless health check for a single thesis against live market data."""
    company_data: CompanyData | None = None
    try:
        company_data = await fetch_company_data(holding.ticker)
    except Exception:
        logger.exception("Failed to fetch company data for %s", holding.ticker)

    if company_data is None:
        return HealthCheckResult(ticker=holding.ticker)

    raw_candidates = generate_monitoring_candidates(
        thesis.interpretation,
        company_data,
        holding.current_price,
    )

    classified = await _classify_candidates(
        thesis,
        raw_candidates,
        ticker=holding.ticker,
        company_name=holding.name,
    )
    watch_hints_status = check_metric_watch_hints(thesis.interpretation, _market_values(company_data))

    return HealthCheckResult(
        ticker=holding.ticker,
        current_price=company_data.current_price,
        sector=company_data.sector,
        pe_ratio=company_data.pe_ratio,
        market_cap=company_data.market_cap,
        upcoming_earnings_date=company_data.upcoming_earnings_date,
        recent_earnings_surprise_pct=company_data.recent_earnings_surprise_pct,
        candidates=classified,
        watch_hints_status=watch_hints_status,
        recent_news_count=len(company_data.news_items),
        thesis_assessment=_assess(classified),
    )
