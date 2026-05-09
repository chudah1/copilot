from app.services.monitoring import check_thesis_metrics, check_price_move


def test_metric_breach_detected():
    key_metrics = [{"metric": "revenue_growth_yoy", "operator": ">=", "threshold": 15.0, "rationale": "Growth driver"}]
    market_values = {"revenue_growth_yoy": 8.0}
    results = check_thesis_metrics(key_metrics, market_values)
    assert len(results) == 1
    assert results[0].breached is True
    assert results[0].metric == "revenue_growth_yoy"
    assert results[0].actual_value == 8.0


def test_no_breach_when_metric_met():
    key_metrics = [{"metric": "revenue_growth_yoy", "operator": ">=", "threshold": 15.0, "rationale": "Growth driver"}]
    market_values = {"revenue_growth_yoy": 20.0}
    results = check_thesis_metrics(key_metrics, market_values)
    assert len(results) == 1
    assert results[0].breached is False


def test_price_move_detection():
    assert check_price_move(current_price=110.0, previous_price=100.0, threshold_pct=10.0) is True
    assert check_price_move(current_price=105.0, previous_price=100.0, threshold_pct=10.0) is False


def test_missing_market_data_skips_metric():
    key_metrics = [{"metric": "revenue_growth_yoy", "operator": ">=", "threshold": 15.0, "rationale": "Growth"}]
    market_values = {}
    results = check_thesis_metrics(key_metrics, market_values)
    assert len(results) == 0
