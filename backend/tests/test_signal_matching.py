import uuid
from unittest.mock import MagicMock

from app.services.decomposition import _watch_hint_from_signal


def _make_signal(signal_type: str, config: dict | None = None, rationale: str | None = None) -> MagicMock:
    signal = MagicMock()
    signal.id = uuid.uuid4()
    signal.signal_type = signal_type
    signal.signal_config_json = config
    signal.rationale = rationale
    signal.signal_label = None
    signal.active = False
    return signal


def _make_active_signal(
    claim_text: str,
    *,
    claim_type: str = "growth",
    signal_type: str,
    signal_label: str,
    rationale: str | None = None,
    position: int = 0,
) -> tuple[MagicMock, MagicMock]:
    signal = _make_signal(signal_type, rationale=rationale)
    signal.signal_label = signal_label
    signal.active = True

    entity = MagicMock()
    entity.signals = [signal]

    claim = MagicMock()
    claim.id = uuid.uuid4()
    claim.claim_type = claim_type
    claim.claim_text = claim_text
    claim.position = position
    claim.entities = [entity]
    return claim, signal


def test_watch_hint_from_signal_includes_ids_price_move():
    signal = _make_signal("price_move", {"threshold_pct": 8.0})
    claim_id = str(uuid.uuid4())
    hint = _watch_hint_from_signal(signal, override_claim_id=claim_id)
    assert hint is not None
    assert hint["kind"] == "price_move_pct"
    assert hint["threshold"] == 8.0
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == claim_id


def test_watch_hint_from_signal_includes_ids_revenue_growth():
    signal = _make_signal("revenue_growth", {"threshold": 0.15, "operator": ">="})
    claim_id = str(uuid.uuid4())
    hint = _watch_hint_from_signal(signal, override_claim_id=claim_id)
    assert hint is not None
    assert hint["kind"] == "metric_threshold"
    assert hint["metric"] == "revenue_growth_yoy"
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == claim_id


def test_watch_hint_from_signal_keeps_metric_specificity_and_converts_threshold_pct():
    signal = _make_signal(
        "revenue_growth",
        {"metric": "services_revenue_growth", "threshold_pct": 16.6, "operator": ">="},
    )

    hint = _watch_hint_from_signal(signal)

    assert hint is not None
    assert hint["metric"] == "services_revenue_growth"
    assert hint["threshold"] == 0.166


def test_watch_hint_from_topic_signal_uses_topic_and_direction():
    signal = _make_signal(
        "transcript_topic",
        {"topic": "Blackwell deployment", "direction": "supports"},
        rationale="Deployment commentary matters.",
    )
    signal.signal_label = "NVDA Blackwell deployment"

    hint = _watch_hint_from_signal(signal)

    assert hint is not None
    assert hint["kind"] == "news_watch"
    assert hint["watch_for"] == "Blackwell deployment"
    assert hint["direction"] == "supports"


def test_normalize_signal_config_backfills_proxy_growth_signal():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="revenue_growth",
        signal_label="SHOP merchant additions growth",
        claim_text="Shopify merchant additions grow consistently to support revenue",
        rationale="Merchant momentum should keep feeding revenue growth.",
        raw_config={},
    )

    assert config["metric"] == "revenue_growth_yoy"
    assert config["operator"] == ">="
    assert config["threshold_pct"] == 0.0
    assert config["proxy_for"] == "SHOP merchant additions growth"


def test_normalize_signal_config_marks_margin_proxy_for_review():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="earnings_growth",
        signal_label="HIMS gross margin trend",
        claim_text="Gross margins stay healthy.",
        rationale="Margin compression would weaken the case.",
        raw_config={"metric": "gross_margin"},
    )

    assert config["metric"] == "earnings_growth_yoy"
    assert config["proxy_for"] == "HIMS gross margin trend"
    assert config["proxy_source_metric"] == "gross_margin"
    assert config["proxy_review_required"] is True


def test_normalize_signal_config_marks_rpo_proxy_for_review():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="revenue_growth",
        signal_label="ORCL remaining performance obligations growth",
        claim_text="Capacity expansion keeps converting into signed customer demand.",
        rationale="RPO indicates contracted future revenue.",
        raw_config={},
    )

    assert config["metric"] == "revenue_growth_yoy"
    assert config["proxy_for"] == "ORCL remaining performance obligations growth"
    assert config["proxy_source_metric"] == "remaining_performance_obligations_growth"
    assert config["proxy_review_required"] is True


def test_normalize_signal_config_marks_transactions_per_consumer_proxy_for_review():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="revenue_growth",
        signal_label="AFRM transactions per active consumer",
        claim_text="Repeat user engagement remains stable or improves.",
        rationale="Usage frequency indicates repeat engagement.",
        raw_config={},
    )

    assert config["metric"] == "revenue_growth_yoy"
    assert config["proxy_for"] == "AFRM transactions per active consumer"
    assert config["proxy_source_metric"] == "transactions_per_active_consumer"
    assert config["proxy_review_required"] is True


def test_normalize_signal_config_infers_double_digit_threshold_from_text():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
        claim_text="Apple Services revenue grows at double-digit rates",
        rationale="Services should keep compounding.",
        raw_config={},
    )

    assert config["threshold_pct"] == 10.0


def test_normalize_signal_config_infers_low_single_digit_threshold_from_text():
    from app.services.decomposition import _normalize_signal_config_json

    config = _normalize_signal_config_json(
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth decline",
        claim_text="Apple Services growth does not fall to low single digits",
        rationale="Low-single-digit Services growth would weaken the case.",
        raw_config={},
    )

    assert config["threshold_pct"] == 5.0


def test_watch_hint_from_signal_includes_ids_earnings_growth():
    signal = _make_signal("earnings_growth", {"threshold": 0.10, "operator": ">="})
    claim_id = str(uuid.uuid4())
    hint = _watch_hint_from_signal(signal, override_claim_id=claim_id)
    assert hint is not None
    assert hint["kind"] == "metric_threshold"
    assert hint["metric"] == "earnings_growth_yoy"
    assert hint["signal_id"] == str(signal.id)
    assert hint["claim_id"] == claim_id


def test_watch_hint_from_signal_does_not_require_entity_relationship():
    signal = _make_signal("price_move", {"threshold_pct": 8.0})
    signal.entity = None

    hint = _watch_hint_from_signal(signal, override_claim_id=None)

    assert hint is not None
    assert hint["claim_id"] is None


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
    claim.entities = []
    return claim


def test_match_candidates_earnings_surprise_binds_to_eps_claim_when_available():
    """Walkthrough on 2026-06-14 found earnings_surprise events binding to
    revenue/growth claims that don't share a metric. EPS surprise should
    prefer claims that are actually about earnings/profit/margin."""
    claims = [
        _make_claim("growth", "Revenue keeps growing driven by iPhone demand", position=0),
        _make_claim("margins", "Operating margin holds above 30%", position=1),
        _make_claim("valuation", "PE ratio is reasonable at current levels", position=2),
    ]
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings missed expectations by 8.2%.",
            "evidence": {"recent_earnings_surprise_pct": -8.2},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    # The margin claim is the EPS-flavored one (margin → earnings), so it wins.
    assert result[0]["evidence"]["claim_id"] == str(claims[1].id)
    assert result[0]["evidence"].get("signal_id") is None


def test_match_candidates_earnings_surprise_leaves_unbound_when_only_revenue_claims():
    """If the thesis has only revenue claims (no EPS/profit/margin), the
    earnings_surprise event should stay unbound rather than misattribute to
    a top-line revenue claim. False attribution is the bug we're fixing."""
    claims = [
        _make_claim("growth", "Data center revenue grows above 20% YoY", position=0),
        _make_claim("growth", "Services revenue keeps growing", position=1),
    ]
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings beat expectations by 5.6%.",
            "evidence": {"recent_earnings_surprise_pct": 5.6},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"].get("claim_id") is None
    assert result[0]["evidence"].get("signal_id") is None


def test_match_candidates_earnings_surprise_does_not_family_bonus_revenue_growth_signal():
    """Even when there's a revenue_growth signal and an earnings_surprise
    event, the family_bonus shouldn't bind them — different metrics."""
    revenue_claim, revenue_signal = _make_active_signal(
        "Data center revenue grows above 20% YoY",
        signal_type="revenue_growth",
        signal_label="NVDA data center revenue growth",
    )
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings beat expectations by 5.6%.",
            "evidence": {"recent_earnings_surprise_pct": 5.6},
        }
    ]
    result = match_candidates_to_signals(candidates, [revenue_claim])
    assert result[0]["evidence"].get("signal_id") is None
    assert result[0]["evidence"].get("claim_id") is None


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


def test_match_candidates_news_or_earnings_candidate():
    claims = [
        _make_claim("growth", "iPhone demand remains strong globally", position=0),
        _make_claim("moat", "Services ecosystem creates lock-in", position=1),
    ]
    candidates = [
        {
            "event_type": "news_or_earnings_candidate",
            "description": "Apple iPhone sales surge in China market",
            "evidence": {"headline": "Apple iPhone sales surge in China market"},
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert result[0]["evidence"]["claim_id"] == str(claims[0].id)


def test_match_candidates_product_ramp_update():
    claim, signal = _make_active_signal(
        "Blackwell deployment remains on plan.",
        signal_type="news_topic",
        signal_label="NVDA Blackwell product cycle deployment",
        rationale="Rollout updates matter.",
    )
    candidates = [
        {
            "event_type": "product_ramp_update",
            "description": "NVIDIA says Blackwell rollout is ahead of plan and supply is improving.",
            "evidence": {"headline": "Blackwell rollout is ahead of plan"},
        }
    ]

    result = match_candidates_to_signals(candidates, [claim])
    assert result[0]["evidence"]["signal_id"] == str(signal.id)


def test_match_candidates_edgar_8k_uses_text_overlap():
    claims = [
        _make_claim("integration", "Eucalyptus acquisition expands international reach", position=0),
        _make_claim("margin", "Gross margin holds above 70%", position=1),
    ]
    candidates = [
        {
            "event_type": "edgar_8k",
            "description": "Hims amended its credit agreement to facilitate the Eucalyptus acquisition and require foreign subsidiaries to join as guarantors after closing.",
            "evidence": {
                "description": "Material Agreement, Other Material Event",
                "items": ["1.01", "8.01"],
            },
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


def test_match_candidates_creates_missing_evidence_dict():
    """Test name purpose: a candidate that arrives without an `evidence` dict
    should still have one created. Originally also asserted that
    earnings_surprise binds to a revenue claim — that was the bug surfaced in
    the 2026-06-14 walkthrough; the matcher now correctly leaves it unbound.
    Switched to an EPS-flavored claim so the binding still demonstrates the
    evidence-dict creation."""
    claims = [_make_claim("margins", "Operating margin stays above 30%", position=0)]
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings missed expectations by 8.2%.",
        }
    ]
    result = match_candidates_to_signals(candidates, claims)
    assert isinstance(result[0]["evidence"], dict)
    assert result[0]["evidence"]["claim_id"] == str(claims[0].id)


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


def test_match_candidates_gemini_news_uses_relevant_signal_label():
    claim, signal = _make_active_signal(
        "Data center demand stays strong",
        signal_type="revenue_growth",
        signal_label="NVDA data center revenue growth",
    )
    candidates = [
        {
            "event_type": "gemini_news",
            "description": "NVDA demand stays strong",
            "evidence": {
                "headline": "NVIDIA reports strong data center demand",
                "relevant_signals": ["NVDA data center revenue growth"],
            },
        }
    ]

    result = match_candidates_to_signals(candidates, [claim])
    assert result[0]["evidence"]["signal_id"] == str(signal.id)
    assert result[0]["evidence"]["claim_id"] == str(claim.id)


def test_match_candidates_gemini_news_multi_label_binds_to_one_active_signal():
    """In production, Gemini often tags a single article with multiple
    relevant_signals (e.g. an AAPL article matching both Services revenue
    growth AND Services gross margin). The matcher binds the candidate to
    one signal_id — verify it picks an active matching signal rather than
    missing the link entirely. relevant_signals is preserved in evidence
    for digest grouping that wants the full set."""
    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services margin stays above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services posts 16% growth with 75% margin",
        "evidence": {
            "headline": "Apple Services Q1 strong on both fronts",
            "relevant_signals": [
                "AAPL Services revenue growth",
                "AAPL Services gross margin trend",
            ],
        },
    }

    result = match_candidates_to_signals([candidate], [rev_claim, margin_claim])
    evidence = result[0]["evidence"]
    assert evidence["signal_id"] in {str(rev_signal.id), str(margin_signal.id)}
    assert evidence["claim_id"] in {str(rev_claim.id), str(margin_claim.id)}
    # Critically, the multi-label list is preserved so downstream grouping
    # can use it instead of being capped by the single bound signal_id.
    assert evidence["relevant_signals"] == [
        "AAPL Services revenue growth",
        "AAPL Services gross margin trend",
    ]


def test_match_candidates_gemini_news_label_match_ignores_inactive_signals():
    """If a label matches an inactive signal but not an active one, the
    candidate should not be bound. Inactive signals are user-rejected or
    expired and should not pull evidence through them."""
    inactive_claim, inactive_signal = _make_active_signal(
        "Old hardware margin claim",
        signal_type="earnings_growth",
        signal_label="AAPL Hardware gross margin trend",
    )
    inactive_signal.active = False  # explicitly inactivate

    candidate = {
        "event_type": "gemini_news",
        "description": "Hardware margin hits 39%",
        "evidence": {
            "headline": "Hardware margin commentary",
            "relevant_signals": ["AAPL Hardware gross margin trend"],
        },
    }

    result = match_candidates_to_signals([candidate], [inactive_claim])
    # Without an active match, the label-based binding falls through; the
    # event_type-driven text-overlap fallback may still set a claim_id, but
    # signal_id stays unset for inactive signals.
    assert result[0]["evidence"].get("signal_id") is None


def test_match_candidates_earnings_family_prefers_active_signal():
    """An earnings_surprise event should prefer an active signal over the
    keyword fallback — but only when the signal is itself in the EPS family
    (earnings_growth, earnings_surprise, guidance_change). The 2026-06-14
    walkthrough surfaced that a revenue_growth signal was getting the
    family-bonus on earnings events, which is wrong (top-line vs bottom-line)."""
    claim, signal = _make_active_signal(
        "Earnings growth must stay strong",
        signal_type="earnings_growth",
        signal_label="AAPL earnings growth",
        rationale="EPS growth should remain healthy.",
    )
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings missed expectations by 8.2%.",
            "evidence": {"recent_earnings_surprise_pct": -8.2},
        }
    ]

    result = match_candidates_to_signals(candidates, [claim])
    assert result[0]["evidence"]["signal_id"] == str(signal.id)
    assert result[0]["evidence"]["claim_id"] == str(claim.id)


def test_match_candidates_insider_prefers_management_signal():
    claim, signal = _make_active_signal(
        "Management discipline matters",
        claim_type="management",
        signal_type="insider_transaction",
        signal_label="AAPL insider selling",
        rationale="Heavy insider selling can weaken confidence in management.",
    )
    candidates = [
        {
            "event_type": "insider_transaction",
            "description": "Apple insider sold shares this week.",
            "evidence": {"transaction_id": "txn-1"},
        }
    ]

    result = match_candidates_to_signals(candidates, [claim])
    assert result[0]["evidence"]["signal_id"] == str(signal.id)
    assert result[0]["evidence"]["claim_id"] == str(claim.id)


def test_build_evidence_summary_tier1_claim_and_signal():
    summary = build_evidence_summary(
        candidate={"description": "Revenue growth slowed to 1.2% YoY."},
        claim_text="Customer demand remains strong",
        signal_label="iPhone unit sales trend",
        why_own_it=None,
        severity="warning",
        verdict="review",
        investor_profile="thesis_driven",
    )
    assert "Your thesis:" in summary
    assert "Customer demand remains strong" in summary
    assert "We were watching:" in summary
    assert "iPhone unit sales trend" in summary
    assert "What changed:" in summary
    assert "Why it matters now:" in summary
    assert "Revenue growth slowed to 1.2% YoY" in summary
    assert "directly threatens" in summary.lower() or "thesis" in summary.lower()
    assert "Re-read the thesis" in summary or "review" in summary.lower()


def test_build_evidence_summary_tier2_claim_only():
    summary = build_evidence_summary(
        candidate={"description": "Earnings surprise was -8.2%."},
        claim_text="Revenue keeps growing",
        signal_label=None,
        why_own_it=None,
        severity="warning",
        verdict="review",
    )
    assert "You said:" in summary
    assert "Revenue keeps growing" in summary
    assert "We watched:" not in summary
    assert "Earnings surprise was -8.2%" in summary


def test_build_evidence_summary_tier3_fallback():
    summary = build_evidence_summary(
        candidate={"description": "Price moved 13.3% since last review."},
        claim_text=None,
        signal_label=None,
        why_own_it="I believe AAPL will keep growing services revenue",
        severity="info",
        verdict="neutral",
    )
    assert "Your reason:" in summary
    assert "I believe AAPL will keep growing services revenue" in summary
    assert "Price moved 13.3%" in summary


def test_build_evidence_summary_for_thesis_driven_profile():
    summary = build_evidence_summary(
        candidate={"description": "Revenue growth slowed materially this quarter."},
        claim_text="Revenue growth must stay strong to support the thesis.",
        signal_label="Revenue Growth",
        why_own_it="Own for durable demand and execution.",
        severity="thesis_breaking",
        verdict="threatens",
        investor_profile="thesis_driven",
    )
    assert 'Your thesis: "Revenue growth must stay strong to support the thesis."' in summary
    assert "We were watching: Revenue Growth" in summary
    assert "Revenue growth slowed materially this quarter." in summary
    assert "directly threatens" in summary.lower()
    assert "Re-read the thesis" in summary


def test_build_evidence_summary_for_hearsay_driven_profile():
    summary = build_evidence_summary(
        candidate={"description": "Management cut guidance after weaker orders."},
        claim_text=None,
        signal_label="Guidance Change",
        why_own_it="AI demand should keep the story alive.",
        severity="warning",
        verdict="review",
        investor_profile="hearsay_driven",
    )
    assert 'Your reason: "AI demand should keep the story alive."' in summary
    assert "Management cut guidance after weaker orders." in summary
    assert "story" in summary.lower()


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


import pytest
from unittest.mock import patch
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.auth import hash_password
from app.services.check_now import run_check_now
from app.services.market_data import CompanyData


@pytest.fixture
async def db_with_decomposition(async_session: AsyncSession):
    """Set up user, holding, thesis, and confirmed decomposition."""
    user = User(email="test-signal@test.com", password_hash=hash_password("pass"))
    async_session.add(user)
    await async_session.flush()

    holding = Holding(
        user_id=user.id,
        ticker="AAPL",
        name="Apple Inc.",
        quantity=10,
        average_cost_basis=150.0,
        currency="USD",
        current_price=150.0,
    )
    async_session.add(holding)
    await async_session.flush()

    thesis = Thesis(
        holding_id=holding.id,
        user_id=user.id,
        status="active",
        thesis_kind="company",
        why_own_it="I believe iPhone demand stays strong",
        confidence="high",
        review_cadence_days=90,
    )
    async_session.add(thesis)
    await async_session.flush()

    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=1,
        status="confirmed",
        reason_type="growth",
        monitorability="high",
    )
    async_session.add(decomposition)
    await async_session.flush()

    claim = ThesisClaim(
        decomposition_id=decomposition.id,
        claim_text="iPhone demand remains strong globally",
        claim_type="growth",
        position=0,
    )
    async_session.add(claim)
    await async_session.flush()

    entity = ThesisEntity(
        claim_id=claim.id,
        entity_name="Apple Inc.",
        entity_ticker="AAPL",
        entity_type="held_company",
        user_confirmed=True,
    )
    async_session.add(entity)
    await async_session.flush()

    signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="price_move",
        signal_label="AAPL share price",
        signal_config_json={"threshold_pct": 5.0},
        rationale="Large price moves warrant review",
        active=True,
        user_confirmed=True,
    )
    async_session.add(signal)
    await async_session.flush()

    # Set interpretation with signal_id/claim_id embedded
    thesis.interpretation = {
        "labels": ["growth"],
        "monitorability": "high",
        "watch_hints": [
            {
                "kind": "price_move_pct",
                "threshold": 5.0,
                "rationale": "Large price moves warrant review",
                "signal_id": str(signal.id),
                "claim_id": str(claim.id),
            }
        ],
        "proxy_signals": [],
        "ambiguity_note": "",
    }
    await async_session.commit()

    return {
        "user": user,
        "holding": holding,
        "thesis": thesis,
        "decomposition": decomposition,
        "claim": claim,
        "entity": entity,
        "signal": signal,
    }


@pytest.mark.asyncio
async def test_check_now_creates_events_with_signal_linking(
    async_session: AsyncSession,
    db_with_decomposition: dict,
):
    """check_now should create events with claim_id, signal_id, evidence_summary, verdict."""
    data = db_with_decomposition
    holding = data["holding"]
    thesis = data["thesis"]
    claim = data["claim"]
    signal = data["signal"]

    # Mock fetch_company_data to return a big price move
    company_data = CompanyData(
        ticker="AAPL",
        name="Apple Inc.",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=180.0,  # 20% move from 150
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
        country="US",
    )

    with patch("app.services.check_now.fetch_company_data", return_value=company_data), \
         patch("app.services.monitoring_pipeline.classify_event", return_value=None):
        result = await run_check_now(holding, thesis, async_session)

    assert result.status == "completed"
    assert result.events_created >= 1

    # Query the created event
    events_result = await async_session.execute(
        sa_select(MonitoringEvent).where(MonitoringEvent.holding_id == holding.id)
    )
    events = events_result.scalars().all()
    price_event = next((e for e in events if e.event_type == "price_move"), None)
    assert price_event is not None
    assert price_event.claim_id == claim.id
    assert price_event.signal_id == signal.id
    assert price_event.evidence_type == "price_move"
    assert price_event.evidence_summary is not None
    assert "You said:" in price_event.evidence_summary
    assert "iPhone demand remains strong" in price_event.evidence_summary
    assert price_event.verdict is not None


def test_multi_signal_binding_records_all_gemini_labels():
    """When Gemini tags an article with multiple relevant_signals, the matcher
    used to bind to one signal_id and drop the rest. Multi-binding preserves
    the full set in matched_signal_ids / matched_signal_labels so downstream
    consumers can attribute the event to every pillar it touches."""
    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services margin above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services growth and margin both strong",
        "evidence": {
            "headline": "Apple Services Q1 strong on growth and margin",
            "relevant_signals": [
                "AAPL Services revenue growth",
                "AAPL Services gross margin trend",
            ],
        },
    }

    result = match_candidates_to_signals([candidate], [rev_claim, margin_claim])
    evidence = result[0]["evidence"]

    # signal_id remains as the primary anchor for backward-compat readers.
    assert evidence["signal_id"] in {str(rev_signal.id), str(margin_signal.id)}

    matched_ids = evidence["matched_signal_ids"]
    matched_labels = evidence["matched_signal_labels"]
    assert str(rev_signal.id) in matched_ids
    assert str(margin_signal.id) in matched_ids
    assert "AAPL Services revenue growth" in matched_labels
    assert "AAPL Services gross margin trend" in matched_labels
    # The primary should appear first so consumers ranking by position get
    # the same ordering as the single-binding fallback.
    assert matched_ids[0] == evidence["signal_id"]


def test_multi_signal_binding_skips_inactive_signals_even_in_relevant_labels():
    """A user-rejected signal should not be in the multi-binding list, even if
    the Gemini relevant_signals payload still references its label."""
    active_claim, active_signal = _make_active_signal(
        "Active claim",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    inactive_claim, inactive_signal = _make_active_signal(
        "Old claim",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )
    inactive_signal.active = False

    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services Q1",
        "evidence": {
            "headline": "Apple Services strong",
            "relevant_signals": [
                "AAPL Services revenue growth",
                "AAPL Services gross margin trend",
            ],
        },
    }
    result = match_candidates_to_signals([candidate], [active_claim, inactive_claim])
    evidence = result[0]["evidence"]
    matched_ids = evidence["matched_signal_ids"]
    assert str(active_signal.id) in matched_ids
    assert str(inactive_signal.id) not in matched_ids


def test_multi_signal_binding_unions_with_word_overlap_matches():
    """Even without explicit relevant_signals, a candidate that scores
    positively against several signals via word overlap should bind to all of
    them. Today's loss is the same: one primary, list ignored."""
    rev_claim, rev_signal = _make_active_signal(
        "Data center revenue grows above 20% YoY",
        signal_type="revenue_growth",
        signal_label="NVDA data center revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Gross margin stays above 70%",
        signal_type="earnings_growth",
        signal_label="NVDA gross margin trend",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Strong NVDA data center revenue growth with healthy gross margin",
        "evidence": {
            "headline": "NVDA reports strong data center revenue growth and gross margin",
        },
    }
    result = match_candidates_to_signals([candidate], [rev_claim, margin_claim])
    evidence = result[0]["evidence"]
    matched_ids = evidence["matched_signal_ids"]
    assert str(rev_signal.id) in matched_ids
    assert str(margin_signal.id) in matched_ids


async def test_embedding_enrichment_binds_semantic_matches_without_word_overlap():
    """Semantic ranking catches matches the word-overlap matcher misses.
    'Pricing Dilemma' and 'Services gross margin' share no words but are
    semantically the same concern."""
    from unittest.mock import patch
    from app.services.signal_matching import enrich_candidates_with_embedding_matches

    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services gross margin stays above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )

    candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "Apple Faces a No-Win Pricing Dilemma",
        "evidence": {"headline": "Apple Faces a No-Win Pricing Dilemma"},
    }

    async def fake_build_similarity(texts):
        margin_text = next(t for t in texts if "gross margin" in t.lower())
        rev_text = next(t for t in texts if "revenue grows" in t.lower())

        def _sim(a: str, b: str) -> float:
            if "Pricing Dilemma" in a and b == margin_text:
                return 0.72
            if "Pricing Dilemma" in a and b == rev_text:
                return 0.30
            return 0.0
        return _sim

    with patch("app.services.news_watch.build_embedding_similarity", new=fake_build_similarity):
        result = await enrich_candidates_with_embedding_matches([candidate], [rev_claim, margin_claim])

    evidence = result[0]["evidence"]
    matched_ids = evidence.get("matched_signal_ids", [])
    assert str(margin_signal.id) in matched_ids
    assert str(rev_signal.id) not in matched_ids
    assert evidence.get("signal_id") == str(margin_signal.id)


async def test_adjudicator_keeps_high_llm_confidence_match_and_overrides_cosine():
    """LLM adjudication on borderline cosine matches replaces the cosine score
    with the LLM's judgment in match_confidence_by_signal."""
    from unittest.mock import patch, MagicMock
    import json
    from app.services.signal_matching import adjudicate_signal_matches

    claim, signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "Apple Services Q1 sales detail",
        "evidence": {
            "headline": "Apple Services Q1 sales detail",
            "matched_signal_ids": [str(signal.id)],
            "matched_signal_labels": ["AAPL Services revenue growth"],
            "match_confidence_by_signal": {str(signal.id): 0.65},  # borderline band
        },
    }

    response_msg = MagicMock(message=MagicMock(content=json.dumps({"confidence": 0.92})))
    response = MagicMock(choices=[response_msg])

    async def fake_create(**kwargs):
        return response

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("app.services.signal_matching.settings.openai_api_key", "test-key", create=True), \
         patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await adjudicate_signal_matches([candidate], [claim])

    evidence = result[0]["evidence"]
    assert evidence["match_confidence_by_signal"][str(signal.id)] == 0.92
    assert str(signal.id) in evidence["matched_signal_ids"]


async def test_adjudicator_drops_false_positive_below_drop_threshold():
    """When the LLM judges the borderline match as a false positive, it gets
    dropped from matched_signal_ids and the confidence map."""
    from unittest.mock import patch, MagicMock
    import json
    from app.services.signal_matching import adjudicate_signal_matches

    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Hardware margin holds",
        signal_type="earnings_growth",
        signal_label="AAPL Hardware gross margin trend",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services Q1 sales detail",
        "evidence": {
            "headline": "Apple Services Q1 sales detail",
            "signal_id": str(margin_signal.id),
            "matched_signal_ids": [str(margin_signal.id), str(rev_signal.id)],
            "matched_signal_labels": ["AAPL Hardware gross margin trend", "AAPL Services revenue growth"],
            "match_confidence_by_signal": {
                str(margin_signal.id): 0.62,
                str(rev_signal.id): 0.78,
            },
        },
    }

    def fake_response(confidence):
        return MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"confidence": confidence})))])

    async def fake_create(**kwargs):
        prompt = kwargs["messages"][0]["content"]
        # margin signal — LLM judges no real connection
        if "Hardware gross margin" in prompt:
            return fake_response(0.20)
        return fake_response(0.85)

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("app.services.signal_matching.settings.openai_api_key", "test-key", create=True), \
         patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await adjudicate_signal_matches([candidate], [rev_claim, margin_claim])

    evidence = result[0]["evidence"]
    assert str(margin_signal.id) not in evidence["matched_signal_ids"]
    assert str(margin_signal.id) not in evidence["match_confidence_by_signal"]
    assert str(rev_signal.id) in evidence["matched_signal_ids"]
    # Primary signal_id should have been promoted to the surviving match
    # since the dropped margin signal was the previous primary.
    assert evidence["signal_id"] == str(rev_signal.id)


async def test_adjudicator_rebuilds_labels_from_remaining_ids_when_labels_repeat():
    """Dropping one signal should not wipe out every identical display label.
    Rebuild labels from the surviving ids so matched_signal_labels stays aligned
    even when two signals share the same text."""
    from unittest.mock import patch, MagicMock
    import json
    from app.services.signal_matching import adjudicate_signal_matches

    first_claim, first_signal = _make_active_signal(
        "Services margin holds",
        signal_type="earnings_growth",
        signal_label="AAPL Services margin",
    )
    second_claim, second_signal = _make_active_signal(
        "Another margin angle",
        signal_type="earnings_growth",
        signal_label="AAPL Services margin",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services profitability mixed",
        "evidence": {
            "headline": "Apple Services profitability mixed",
            "signal_id": str(first_signal.id),
            "matched_signal_ids": [str(first_signal.id), str(second_signal.id)],
            "matched_signal_labels": ["AAPL Services margin", "AAPL Services margin"],
            "match_confidence_by_signal": {
                str(first_signal.id): 0.62,
                str(second_signal.id): 0.78,
            },
        },
    }

    def fake_response(confidence):
        return MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"confidence": confidence})))])

    async def fake_create(**kwargs):
        prompt = kwargs["messages"][0]["content"]
        if "Services margin" in prompt and "Services margin holds" in prompt:
            return fake_response(0.20)
        return fake_response(0.86)

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("app.services.signal_matching.settings.openai_api_key", "test-key", create=True), \
         patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await adjudicate_signal_matches([candidate], [first_claim, second_claim])

    evidence = result[0]["evidence"]
    assert evidence["matched_signal_ids"] == [str(second_signal.id)]
    assert evidence["matched_signal_labels"] == ["AAPL Services margin"]
    assert evidence["signal_id"] == str(second_signal.id)


async def test_adjudicator_skips_high_cosine_confident_matches():
    """Matches above the ceiling (default 0.85) are confident enough on cosine
    alone; the LLM should never be called for them."""
    from unittest.mock import patch, MagicMock
    from app.services.signal_matching import adjudicate_signal_matches

    claim, signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    candidate = {
        "event_type": "news_or_earnings_candidate",
        "evidence": {
            "headline": "AAPL Services revenue grew 15%",
            "matched_signal_ids": [str(signal.id)],
            "match_confidence_by_signal": {str(signal.id): 0.92},  # above ceiling
        },
    }

    called = {"count": 0}

    async def fake_create(**kwargs):
        called["count"] += 1
        raise AssertionError("LLM should not be called for above-ceiling matches")

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("app.services.signal_matching.settings.openai_api_key", "test-key", create=True), \
         patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await adjudicate_signal_matches([candidate], [claim])

    assert called["count"] == 0
    assert result[0]["evidence"]["match_confidence_by_signal"][str(signal.id)] == 0.92


async def test_adjudicator_no_op_without_openai_key():
    """No API key → don't try, don't crash, don't change anything."""
    from unittest.mock import patch
    from app.services.signal_matching import adjudicate_signal_matches

    claim, signal = _make_active_signal(
        "x",
        signal_type="revenue_growth",
        signal_label="X",
    )
    candidate = {
        "event_type": "news_or_earnings_candidate",
        "evidence": {
            "matched_signal_ids": [str(signal.id)],
            "match_confidence_by_signal": {str(signal.id): 0.70},
        },
    }
    with patch("app.services.signal_matching.settings.openai_api_key", "", create=True):
        result = await adjudicate_signal_matches([candidate], [claim])
    assert result[0]["evidence"]["match_confidence_by_signal"][str(signal.id)] == 0.70


async def test_embedding_enrichment_records_cosine_confidence_per_signal():
    """Cosine scores from the embedding pass land in
    evidence.match_confidence_by_signal so the UI can render strong matches
    differently from weakly-inferred ones. Gemini explicit-label matches and
    pre-bound signals are intentionally absent — their omission is the signal
    that the match was high-confidence by other means."""
    from unittest.mock import patch
    from app.services.signal_matching import enrich_candidates_with_embedding_matches

    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services gross margin stays above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )

    candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "Apple Faces a No-Win Pricing Dilemma",
        "evidence": {"headline": "Apple Faces a No-Win Pricing Dilemma"},
    }

    async def fake_build_similarity(texts):
        def _sim(a: str, b: str) -> float:
            if "gross margin" in b.lower():
                return 0.78
            if "revenue grows" in b.lower():
                return 0.65
            return 0.0
        return _sim

    with patch("app.services.news_watch.build_embedding_similarity", new=fake_build_similarity):
        result = await enrich_candidates_with_embedding_matches([candidate], [rev_claim, margin_claim])

    confidence = result[0]["evidence"]["match_confidence_by_signal"]
    assert confidence[str(margin_signal.id)] == 0.78
    assert confidence[str(rev_signal.id)] == 0.65


async def test_embedding_enrichment_unions_with_existing_multi_binding():
    """When match_candidates_to_signals already bound one signal via Gemini
    labels, the embedding pass adds further semantic matches on top — not
    replacing them."""
    from unittest.mock import patch
    from app.services.signal_matching import enrich_candidates_with_embedding_matches

    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services gross margin stays above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )

    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services Q1 strong",
        "evidence": {
            "headline": "Apple Services Q1 strong",
            "signal_id": str(rev_signal.id),
            "matched_signal_ids": [str(rev_signal.id)],
            "matched_signal_labels": ["AAPL Services revenue growth"],
        },
    }

    async def fake_build_similarity(texts):
        def _sim(a: str, b: str) -> float:
            return 0.80 if "gross margin" in b.lower() else 0.10
        return _sim

    with patch("app.services.news_watch.build_embedding_similarity", new=fake_build_similarity):
        result = await enrich_candidates_with_embedding_matches([candidate], [rev_claim, margin_claim])

    evidence = result[0]["evidence"]
    assert evidence["signal_id"] == str(rev_signal.id)
    assert str(rev_signal.id) in evidence["matched_signal_ids"]
    assert str(margin_signal.id) in evidence["matched_signal_ids"]


async def test_embedding_enrichment_skips_quantitative_event_types():
    """price_move, watch_hint_breach, metric_threshold etc. are already
    pre-bound to specific signals; the embedding pass should not pull in
    semantically-near other signals on top."""
    from unittest.mock import patch
    from app.services.signal_matching import enrich_candidates_with_embedding_matches

    claim, signal = _make_active_signal(
        "Price holds floor",
        signal_type="price_move",
        signal_label="NVDA price floor",
    )

    candidate = {
        "event_type": "price_move",
        "description": "NVDA down 12%",
        "evidence": {"signal_id": str(signal.id), "price_change_pct": -12.0},
    }

    called = {"build": False}

    async def fake_build_similarity(texts):
        called["build"] = True
        return lambda a, b: 0.9

    with patch("app.services.news_watch.build_embedding_similarity", new=fake_build_similarity):
        result = await enrich_candidates_with_embedding_matches([candidate], [claim])

    assert called["build"] is False
    assert result[0]["evidence"]["signal_id"] == str(signal.id)


def test_multi_signal_binding_records_primary_when_upstream_pre_bound():
    """Some events arrive pre-bound (price_move, watch_hint_breach, news_watch)
    with signal_id already set. The multi-binding list should still get
    populated so consumers can rely on it being present, even if it only
    contains the primary."""
    claim, signal = _make_active_signal(
        "Price holds above floor",
        signal_type="price_move",
        signal_label="NVDA price floor",
    )
    candidate = {
        "event_type": "price_move",
        "description": "NVDA down 12%",
        "evidence": {"signal_id": str(signal.id), "price_change_pct": -12.0},
    }
    result = match_candidates_to_signals([candidate], [claim])
    evidence = result[0]["evidence"]
    assert evidence["matched_signal_ids"] == [str(signal.id)]
    assert evidence["matched_signal_labels"] == ["NVDA price floor"]


def test_multi_signal_binding_does_not_bind_unrelated_news_signals_by_family_only():
    """A generic news-topic family bonus should not bind unrelated qualitative
    signals when there is zero text overlap with the candidate."""
    demand_claim, demand_signal = _make_active_signal(
        "MI350 demand stays strong",
        signal_type="news_topic",
        signal_label="AMD MI350 demand commentary",
    )
    gaming_claim, gaming_signal = _make_active_signal(
        "Gaming demand stabilizes",
        signal_type="news_topic",
        signal_label="AMD Radeon gaming demand commentary",
        position=1,
    )
    candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "AMD adds new enterprise sales leader",
        "evidence": {"headline": "AMD appoints new enterprise sales leader"},
    }

    result = match_candidates_to_signals([candidate], [demand_claim, gaming_claim])
    evidence = result[0]["evidence"]
    assert evidence.get("signal_id") is None
    assert evidence.get("matched_signal_ids") is None
    assert evidence.get("matched_signal_labels") is None


def test_multi_signal_binding_merges_relevance_labels_for_prebound_candidates():
    """If an upstream stage pre-bound signal_id and a later LLM stage adds
    relevant_signals, the matcher should widen the multi-binding list instead
    of freezing at the primary only."""
    rev_claim, rev_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    margin_claim, margin_signal = _make_active_signal(
        "Services margin above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )
    candidate = {
        "event_type": "gemini_news",
        "description": "Apple Services strong on growth and margin",
        "evidence": {
            "signal_id": str(rev_signal.id),
            "relevant_signals": [
                "AAPL Services revenue growth",
                "AAPL Services gross margin trend",
            ],
        },
    }

    result = match_candidates_to_signals([candidate], [rev_claim, margin_claim])
    evidence = result[0]["evidence"]
    assert evidence["matched_signal_ids"] == [str(rev_signal.id), str(margin_signal.id)]
    assert evidence["matched_signal_labels"] == [
        "AAPL Services revenue growth",
        "AAPL Services gross margin trend",
    ]


async def test_embedding_enrichment_sets_primary_to_highest_similarity_match():
    """When a candidate has no primary signal yet, the embedding pass should
    anchor signal_id to the strongest semantic match, not whichever signal was
    iterated first."""
    from unittest.mock import patch
    from app.services.signal_matching import enrich_candidates_with_embedding_matches

    lower_claim, lower_signal = _make_active_signal(
        "Services revenue grows",
        signal_type="revenue_growth",
        signal_label="AAPL Services revenue growth",
    )
    higher_claim, higher_signal = _make_active_signal(
        "Services gross margin stays above 72%",
        signal_type="earnings_growth",
        signal_label="AAPL Services gross margin trend",
        position=1,
    )

    candidate = {
        "event_type": "news_or_earnings_candidate",
        "description": "Apple faces pricing pressure in Services",
        "evidence": {"headline": "Apple faces pricing pressure in Services"},
    }

    async def fake_build_similarity(texts):
        low_text = next(t for t in texts if "revenue grows" in t.lower())
        high_text = next(t for t in texts if "gross margin" in t.lower())

        def _sim(a: str, b: str) -> float:
            if "pricing pressure" in a.lower() and b == low_text:
                return 0.62
            if "pricing pressure" in a.lower() and b == high_text:
                return 0.81
            return 0.0
        return _sim

    with patch("app.services.news_watch.build_embedding_similarity", new=fake_build_similarity):
        result = await enrich_candidates_with_embedding_matches([candidate], [lower_claim, higher_claim])

    evidence = result[0]["evidence"]
    assert evidence["signal_id"] == str(higher_signal.id)
    assert evidence["matched_signal_ids"] == [str(higher_signal.id), str(lower_signal.id)]
