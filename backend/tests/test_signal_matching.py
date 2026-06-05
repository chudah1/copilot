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
    claims = [_make_claim("growth", "Revenue keeps growing", position=0)]
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was -8.2%.",
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


def test_match_candidates_earnings_family_prefers_active_signal():
    claim, signal = _make_active_signal(
        "Revenue growth must stay strong",
        signal_type="revenue_growth",
        signal_label="AAPL revenue growth",
        rationale="Revenue growth should remain healthy.",
    )
    candidates = [
        {
            "event_type": "earnings_surprise",
            "description": "Recent earnings surprise was -8.2%.",
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
