import operator
from dataclasses import dataclass

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


def check_thesis_metrics(key_metrics: list[dict], market_values: dict[str, float]) -> list[RuleCheckResult]:
    results = []
    for km in key_metrics:
        metric_name = km["metric"]
        if metric_name not in market_values:
            continue
        actual = market_values[metric_name]
        op_str = km["operator"]
        threshold = km["threshold"]
        op_func = OPERATORS.get(op_str)
        if op_func is None:
            continue
        met = op_func(actual, threshold)
        results.append(RuleCheckResult(metric=metric_name, operator=op_str, threshold=threshold, actual_value=actual, breached=not met, rationale=km.get("rationale", "")))
    return results


def check_price_move(current_price: float, previous_price: float, threshold_pct: float = 10.0) -> bool:
    if previous_price == 0:
        return False
    pct_change = abs((current_price - previous_price) / previous_price) * 100
    return pct_change >= threshold_pct
