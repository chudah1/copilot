import operator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.services.market_data import CompanyData, shortlist_qualitative_candidates

OPERATORS = {
    ">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt, "==": operator.eq,
}


@dataclass
class RuleCheckResult:
    metric: str
    operator: str
    threshold: float
    actual_value: float
    breached: bool
    rationale: str
    signal_id: str | None = None
    claim_id: str | None = None


def extract_watch_hints(interpretation: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not interpretation:
        return []
    hints = interpretation.get("watch_hints", [])
    if isinstance(hints, list):
        return [hint for hint in hints if isinstance(hint, dict)]
    return []


def check_metric_watch_hints(
    interpretation: dict[str, Any] | None,
    market_values: dict[str, float],
) -> list[RuleCheckResult]:
    results = []
    for hint in extract_watch_hints(interpretation):
        if hint.get("kind") != "metric_threshold":
            continue
        metric_name = hint.get("metric")
        if metric_name not in market_values:
            continue
        actual = market_values[metric_name]
        op_str = hint.get("operator")
        threshold = hint.get("threshold")
        op_func = OPERATORS.get(op_str)
        if op_func is None or threshold is None:
            continue
        met = op_func(actual, threshold)
        results.append(
            RuleCheckResult(
                metric=metric_name,
                operator=op_str,
                threshold=threshold,
                actual_value=actual,
                breached=not met,
                rationale=hint.get("rationale", ""),
                signal_id=hint.get("signal_id"),
                claim_id=hint.get("claim_id"),
            )
        )
    return results


DEFAULT_PRICE_THRESHOLD_PCT = 5.0

DEFAULT_WATCH_HINTS: list[dict[str, Any]] = [
    {
        "kind": "price_move_pct",
        "threshold": DEFAULT_PRICE_THRESHOLD_PCT,
        "rationale": "Review when price moves sharply.",
    }
]


@dataclass
class PriceWatchInfo:
    threshold: float
    signal_id: str | None = None
    claim_id: str | None = None


def get_price_watch_info(interpretation: dict[str, Any] | None, default: float = DEFAULT_PRICE_THRESHOLD_PCT) -> PriceWatchInfo:
    hints = extract_watch_hints(interpretation)
    for hint in hints:
        if hint.get("kind") == "price_move_pct":
            threshold = hint.get("threshold")
            if isinstance(threshold, (int, float)):
                return PriceWatchInfo(
                    threshold=float(threshold),
                    signal_id=hint.get("signal_id"),
                    claim_id=hint.get("claim_id"),
                )
    return PriceWatchInfo(threshold=default)


def get_price_watch_threshold(interpretation: dict[str, Any] | None, default: float = DEFAULT_PRICE_THRESHOLD_PCT) -> float | None:
    return get_price_watch_info(interpretation, default).threshold


def check_price_move(current_price: float, previous_price: float, threshold_pct: float = 10.0) -> bool:
    if previous_price == 0:
        return False
    pct_change = abs((current_price - previous_price) / previous_price) * 100
    return pct_change >= threshold_pct


def _effective_interpretation(interpretation: dict[str, Any] | None) -> dict[str, Any]:
    """Return interpretation with default watch_hints if missing or empty."""
    if not interpretation or not interpretation.get("watch_hints"):
        return {"watch_hints": DEFAULT_WATCH_HINTS}
    return interpretation


def generate_monitoring_candidates(
    interpretation: dict[str, Any] | None,
    company_data: CompanyData | None,
    previous_price: float | None,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    if company_data is None:
        return []

    effective = _effective_interpretation(interpretation)
    candidates: list[dict[str, Any]] = []
    normalized_now = now or datetime.now(timezone.utc)

    price_info = get_price_watch_info(effective)
    if (
        price_info.threshold is not None
        and company_data.current_price is not None
        and previous_price is not None
        and check_price_move(company_data.current_price, previous_price, price_info.threshold)
    ):
        pct_change = abs((company_data.current_price - previous_price) / previous_price) * 100
        evidence: dict[str, Any] = {
            "current_price": company_data.current_price,
            "previous_price": previous_price,
            "threshold_pct": price_info.threshold,
        }
        if price_info.signal_id:
            evidence["signal_id"] = price_info.signal_id
        if price_info.claim_id:
            evidence["claim_id"] = price_info.claim_id
        candidates.append(
            {
                "event_type": "price_move",
                "description": f"Price moved {pct_change:.1f}% since the last recorded price.",
                "evidence": evidence,
            }
        )

    market_values = {
        "revenue_growth_yoy": company_data.revenue_growth_yoy,
        "earnings_growth_yoy": company_data.earnings_growth_yoy,
        "pe_ratio": company_data.pe_ratio,
        "dividend_yield": company_data.dividend_yield,
    }
    market_values = {k: v for k, v in market_values.items() if v is not None}
    for breach in check_metric_watch_hints(effective, market_values):
        if breach.breached:
            evidence = {
                "metric": breach.metric,
                "actual_value": breach.actual_value,
                "operator": breach.operator,
                "threshold": breach.threshold,
                "rationale": breach.rationale,
            }
            if breach.signal_id:
                evidence["signal_id"] = breach.signal_id
            if breach.claim_id:
                evidence["claim_id"] = breach.claim_id
            candidates.append(
                {
                    "event_type": "metric_threshold",
                    "description": (
                        f"Watch hint breached: {breach.metric} is {breach.actual_value} "
                        f"(expected {breach.operator} {breach.threshold})."
                    ),
                    "evidence": evidence,
                }
            )

    candidates.extend(
        shortlist_qualitative_candidates(
            company_data.news_items,
            company_data.recent_earnings_surprise_pct,
            company_data.upcoming_earnings_date,
            getattr(company_data, "earnings_call", None),
            getattr(company_data, "insider_transactions", []),
            now=normalized_now,
        )
    )

    return candidates
