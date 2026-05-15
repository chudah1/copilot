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


from app.services.signal_matching import (
    build_evidence_summary,
    determine_verdict,
    match_candidates_to_signals,
)


def _make_claim(claim_type: str, claim_text: str, position: int = 0) -> MagicMock:
    claim = MagicMock()
    claim.id = uuid.uuid4()
    claim.claim_type = claim_type
    claim.claim_text = claim_text
    claim.position = position
    return claim


def test_match_candidates_earnings_surprise():
    claims = [
        _make_claim("growth", "Revenue keeps growing driven by iPhone demand", position=0),
        _make_claim("valuation", "PE ratio is reasonable at current levels", position=1),
    ]
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was -8.2%.",
            "evidence": {"recent_earnings_surprise_pct": -8.2},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"]["claim_id"] == str(claims[0].id)
    assert result[0]["evidence"].get("signal_id") is None


def test_match_candidates_upcoming_earnings():
    claims = [
        _make_claim("earnings", "Earnings growth is accelerating", position=0),
        _make_claim("moat", "Brand loyalty creates pricing power", position=1),
    ]
    candidates = [
        {
            "event_type": "upcoming_earnings",
            "description": "Earnings are scheduled for 2026-06-01.",
            "evidence": {"upcoming_earnings_date": "2026-06-01"},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"]["claim_id"] == str(claims[0].id)


def test_match_candidates_news_keyword():
    claims = [
        _make_claim("growth", "iPhone demand remains strong globally", position=0),
        _make_claim("moat", "Services ecosystem creates lock-in", position=1),
    ]
    candidates = [
        {
            "event_type": "news_keyword",
            "description": "Apple iPhone sales surge in China market",
            "evidence": {"headline": "Apple iPhone sales surge in China market"},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"]["claim_id"] == str(claims[0].id)


def test_match_candidates_no_claims():
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was -8.2%.",
            "evidence": {"recent_earnings_surprise_pct": -8.2},
        }
    ]
    result = match_candidates_to_signals(candidates, None)
    assert "claim_id" not in result[0]["evidence"]


def test_match_candidates_already_has_signal_id():
    signal_id = str(uuid.uuid4())
    claim_id = str(uuid.uuid4())
    claims = [_make_claim("growth", "Revenue keeps growing", position=0)]
    candidates = [
        {
            "event_type": "price_move",
            "description": "Price moved 15%.",
            "evidence": {"signal_id": signal_id, "claim_id": claim_id},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"]["signal_id"] == signal_id
    assert result[0]["evidence"]["claim_id"] == claim_id


def test_build_evidence_summary_tier1_claim_and_signal():
    summary = build_evidence_summary(
        candidate={"description": "Revenue growth slowed to 1.2% YoY."},
        claim_text="Customer demand remains strong",
        signal_label="iPhone unit sales trend",
        why_own_it=None,
    )
    assert "You said:" in summary
    assert "Customer demand remains strong" in summary
    assert "We watched:" in summary
    assert "iPhone unit sales trend" in summary
    assert "What happened:" in summary
    assert "Revenue growth slowed to 1.2% YoY" in summary


def test_build_evidence_summary_tier2_claim_only():
    summary = build_evidence_summary(
        candidate={"description": "Earnings surprise was -8.2%."},
        claim_text="Revenue keeps growing",
        signal_label=None,
        why_own_it=None,
    )
    assert "You said:" in summary
    assert "Revenue keeps growing" in summary
    assert "We watched:" not in summary
    assert "What happened:" in summary


def test_build_evidence_summary_tier3_fallback():
    summary = build_evidence_summary(
        candidate={"description": "Price moved 13.3% since last review."},
        claim_text=None,
        signal_label=None,
        why_own_it="I believe AAPL will keep growing services revenue",
    )
    assert "Your reason:" in summary
    assert "I believe AAPL will keep growing services revenue" in summary
    assert "What happened:" in summary


def test_build_evidence_summary_no_context():
    summary = build_evidence_summary(
        candidate={"description": "Price moved 13.3%."},
        claim_text=None,
        signal_label=None,
        why_own_it=None,
    )
    assert summary == "Price moved 13.3%."


def test_determine_verdict_thesis_breaking():
    assert determine_verdict("thesis_breaking") == "threatens"


def test_determine_verdict_warning():
    assert determine_verdict("warning") == "review"


def test_determine_verdict_info():
    assert determine_verdict("info") == "neutral"


def test_determine_verdict_unknown_defaults_to_review():
    assert determine_verdict("something_else") == "review"
