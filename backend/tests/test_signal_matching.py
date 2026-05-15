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
