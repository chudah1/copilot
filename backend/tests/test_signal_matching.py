import uuid
from unittest.mock import MagicMock

from app.services.decomposition import _watch_hint_from_signal


def _make_signal(signal_type: str, config: dict | None = None, rationale: str | None = None) -> MagicMock:
    signal = MagicMock()
    signal.id = uuid.uuid4()
    signal.signal_type = signal_type
    signal.signal_config_json = config
    signal.rationale = rationale
    # Entity with claim_id
    signal.entity = MagicMock()
    signal.entity.claim_id = uuid.uuid4()
    return signal


def test_watch_hint_from_signal_includes_ids_price_move():
    signal = _make_signal("price_move", {"threshold_pct": 8.0})
    hint = _watch_hint_from_signal(signal)
    assert hint is not None
    assert hint["kind"] == "price_move_pct"
    assert hint["threshold"] == 8.0
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == str(signal.entity.claim_id)


def test_watch_hint_from_signal_includes_ids_revenue_growth():
    signal = _make_signal("revenue_growth", {"threshold": 0.15, "operator": ">="})
    hint = _watch_hint_from_signal(signal)
    assert hint is not None
    assert hint["kind"] == "metric_threshold"
    assert hint["metric"] == "revenue_growth_yoy"
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == str(signal.entity.claim_id)


def test_watch_hint_from_signal_includes_ids_earnings_growth():
    signal = _make_signal("earnings_growth", {"threshold": 0.10, "operator": ">="})
    hint = _watch_hint_from_signal(signal)
    assert hint is not None
    assert hint["kind"] == "metric_threshold"
    assert hint["metric"] == "earnings_growth_yoy"
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == str(signal.entity.claim_id)


def test_watch_hint_from_signal_unknown_type_returns_none():
    signal = _make_signal("unknown_type")
    hint = _watch_hint_from_signal(signal)
    assert hint is None


from app.services.monitoring import (
    check_metric_watch_hints,
    generate_monitoring_candidates,
)
from app.services.market_data import CompanyData


def test_check_metric_watch_hints_carries_signal_ids():
    signal_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    interpretation = {
        "watch_hints": [
            {
                "kind": "metric_threshold",
                "metric": "revenue_growth_yoy",
                "operator": ">=",
                "threshold": 15.0,
                "rationale": "Growth driver",
                "signal_id": signal_id,
                "claim_id": claim_id,
            }
        ]
    }
    market_values = {"revenue_growth_yoy": 8.0}
    results = check_metric_watch_hints(interpretation, market_values)
    assert len(results) == 1
    assert results[0].breached is True
    assert results[0].signal_id == signal_id
    assert results[0].claim_id == claim_id


def test_check_metric_watch_hints_works_without_ids():
    interpretation = {
        "watch_hints": [
            {
                "kind": "metric_threshold",
                "metric": "revenue_growth_yoy",
                "operator": ">=",
                "threshold": 15.0,
                "rationale": "Growth driver",
            }
        ]
    }
    market_values = {"revenue_growth_yoy": 8.0}
    results = check_metric_watch_hints(interpretation, market_values)
    assert len(results) == 1
    assert results[0].signal_id is None
    assert results[0].claim_id is None


def test_generate_candidates_price_move_carries_ids():
    signal_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    interpretation = {
        "watch_hints": [
            {
                "kind": "price_move_pct",
                "threshold": 5.0,
                "rationale": "Review on big moves.",
                "signal_id": signal_id,
                "claim_id": claim_id,
            }
        ]
    }
    company_data = CompanyData(
        ticker="AAPL",
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=120.0,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        pe_ratio=None,
        market_cap=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
    )
    candidates = generate_monitoring_candidates(interpretation, company_data, 100.0)
    price_candidates = [c for c in candidates if c["event_type"] == "price_move"]
    assert len(price_candidates) == 1
    assert price_candidates[0]["evidence"]["signal_id"] == signal_id
    assert price_candidates[0]["evidence"]["claim_id"] == claim_id


def test_generate_candidates_metric_breach_carries_ids():
    signal_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    interpretation = {
        "watch_hints": [
            {
                "kind": "metric_threshold",
                "metric": "revenue_growth_yoy",
                "operator": ">=",
                "threshold": 15.0,
                "rationale": "Growth driver",
                "signal_id": signal_id,
                "claim_id": claim_id,
            }
        ]
    }
    company_data = CompanyData(
        ticker="AAPL",
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=150.0,
        revenue_growth_yoy=8.0,
        earnings_growth_yoy=None,
        pe_ratio=None,
        market_cap=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
    )
    candidates = generate_monitoring_candidates(interpretation, company_data, 150.0)
    metric_candidates = [c for c in candidates if c["event_type"] == "metric_threshold"]
    assert len(metric_candidates) == 1
    assert metric_candidates[0]["evidence"]["signal_id"] == signal_id
    assert metric_candidates[0]["evidence"]["claim_id"] == claim_id
