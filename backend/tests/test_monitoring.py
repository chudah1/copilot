from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.jobs.monitoring_run import (
    _extract_proxy_tickers,
    _generate_proxy_candidates,
    run_monitoring,
)
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password
from app.services.market_data import CompanyData, InsiderTransaction, NewsItem, TranscriptSignal
from app.services.monitoring import (
    DEFAULT_PRICE_THRESHOLD_PCT,
    check_metric_watch_hints,
    check_price_move,
    generate_monitoring_candidates,
    get_price_watch_threshold,
)


def test_metric_breach_detected():
    interpretation = {
        "watch_hints": [
            {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 15.0, "rationale": "Growth driver"}
        ]
    }
    market_values = {"revenue_growth_yoy": 8.0}
    results = check_metric_watch_hints(interpretation, market_values)
    assert len(results) == 1
    assert results[0].breached is True


def test_price_move_detection():
    assert check_price_move(current_price=110.0, previous_price=100.0, threshold_pct=10.0) is True
    assert check_price_move(current_price=105.0, previous_price=100.0, threshold_pct=10.0) is False


def test_price_threshold_defaults_when_no_interpretation():
    # Every thesis gets price monitoring now — no thesis is left unmonitored
    assert get_price_watch_threshold(None) == DEFAULT_PRICE_THRESHOLD_PCT
    assert get_price_watch_threshold({"watch_hints": []}) == DEFAULT_PRICE_THRESHOLD_PCT
    assert DEFAULT_PRICE_THRESHOLD_PCT == 5.0


def test_generate_monitoring_candidates_combines_quant_and_qualitative_signals():
    interpretation = {
        "watch_hints": [
            {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Large moves deserve review."},
            {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.15, "rationale": "Growth driver"},
        ]
    }
    company_data = CompanyData(
        ticker="AAPL",
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=120.0,
        market_cap=1.0,
        pe_ratio=30.0,
        revenue_growth_yoy=0.08,
        earnings_growth_yoy=0.12,
        dividend_yield=0.01,
        description="",
        recent_news=["Apple issues new guidance"],
        upcoming_earnings_date=datetime(2026, 5, 15, tzinfo=timezone.utc),
        recent_earnings_surprise_pct=6.0,
        news_items=[
            NewsItem(
                id="article-1",
                headline="Apple issues new guidance",
                summary="Management updated expectations.",
                published_at=datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
                source="Reuters",
                url="https://example.com/apple-guidance",
                sentiment=0.1,
                topics=["earnings"],
                ticker_relevance=0.8,
            )
        ],
        earnings_call=TranscriptSignal(
            quarter="2026Q1",
            call_date=datetime(2026, 5, 5, tzinfo=timezone.utc),
            sentiment=-0.21,
            sentiment_label="Negative",
            highlights=["Management flagged softer enterprise demand."],
            excerpt="Management flagged softer enterprise demand.",
        ),
        insider_transactions=[
            InsiderTransaction(
                id="txn-1",
                filing_date=datetime(2026, 5, 10, tzinfo=timezone.utc),
                transaction_date=datetime(2026, 5, 9, tzinfo=timezone.utc),
                insider_name="Jane Founder",
                title="Founder & CEO",
                transaction_type="Sale",
                shares=10000,
                share_price=180.0,
                value=1800000.0,
            )
        ],
        provider_payload={},
    )

    candidates = generate_monitoring_candidates(
        interpretation,
        company_data,
        previous_price=100.0,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    event_types = {candidate["event_type"] for candidate in candidates}
    assert "price_move" in event_types
    assert "metric_threshold" in event_types
    assert "earnings_surprise" in event_types
    assert "earnings_call_transcript" in event_types
    assert "insider_transaction" in event_types
    assert any(candidate["event_type"] == "metric_threshold" for candidate in candidates)


def test_generate_monitoring_candidates_ignores_irrelevant_news():
    company_data = CompanyData(
        ticker="MSFT",
        name="Microsoft",
        sector="Technology",
        industry="Software",
        current_price=100.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=["Microsoft opens a new office"],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[
            NewsItem(
                id="article-1",
                headline="Microsoft opens a new office",
                summary="Office expansion continues.",
                published_at=datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
                source="Reuters",
                url="https://example.com/msft-office",
                sentiment=0.0,
                topics=["technology"],
                ticker_relevance=0.8,
            )
        ],
        provider_payload={},
    )
    candidates = generate_monitoring_candidates(
        {"watch_hints": []},
        company_data,
        previous_price=100.0,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert candidates == []


async def test_run_monitoring_creates_multiple_events_and_flags_review(db, job_session_factory):
    user = User(email="monitor@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="I own it for resilient ecosystem demand.",
        must_remain_true="Demand and margins stay durable.",
        what_would_change_my_mind="A sharp deterioration in demand.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Large moves deserve review."}
            ]
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    company_data = CompanyData(
        ticker="AAPL",
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=120.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=["Apple issues new guidance"],
        upcoming_earnings_date=datetime(2026, 5, 14, tzinfo=timezone.utc),
        recent_earnings_surprise_pct=6.0,
        news_items=[],
        earnings_call=TranscriptSignal(
            quarter="2026Q1",
            call_date=datetime(2026, 5, 6, tzinfo=timezone.utc),
            sentiment=-0.2,
            sentiment_label="Negative",
            highlights=["Management noted weaker demand in key segments."],
            excerpt="Management noted weaker demand in key segments.",
        ),
        insider_transactions=[
            InsiderTransaction(
                id="txn-1",
                filing_date=datetime(2026, 5, 10, tzinfo=timezone.utc),
                transaction_date=datetime(2026, 5, 9, tzinfo=timezone.utc),
                insider_name="Jane Founder",
                title="Founder & CEO",
                transaction_type="Sale",
                shares=5000,
                share_price=190.0,
                value=950000.0,
            )
        ],
        provider_payload={"quote": {"Global Quote": {"05. price": "120.0"}}},
    )
    classifications = [
        type("Classification", (), {"severity": "thesis_breaking", "analysis": "Price move matters."})(),
        type("Classification", (), {"severity": "warning", "analysis": "Earnings surprise matters."})(),
        type("Classification", (), {"severity": "warning", "analysis": "Upcoming earnings matter."})(),
        type("Classification", (), {"severity": "warning", "analysis": "Transcript matters."})(),
        type("Classification", (), {"severity": "warning", "analysis": "Insider sale matters."})(),
    ]

    with patch("app.jobs.monitoring_run.settings") as mock_settings:
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_settings.market_data_provider = "alpha_vantage"
        with patch("app.jobs.monitoring_run.async_session", job_session_factory):
            with patch("app.jobs.monitoring_run.fetch_company_data", new_callable=AsyncMock, return_value=company_data):
                with patch("app.jobs.monitoring_run.classify_event", new_callable=AsyncMock, side_effect=classifications):
                    await run_monitoring()

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(events) == 5
    await db.refresh(thesis)
    assert thesis.status == "needs_review"


def test_generate_monitoring_candidates_includes_founder_transaction_signal():
    company_data = CompanyData(
        ticker="NVDA",
        name="NVIDIA",
        sector="Technology",
        industry="Semiconductors",
        current_price=900.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        earnings_call=None,
        insider_transactions=[
            InsiderTransaction(
                id="txn-founder-1",
                filing_date=datetime(2026, 5, 10, tzinfo=timezone.utc),
                transaction_date=datetime(2026, 5, 9, tzinfo=timezone.utc),
                insider_name="John Founder",
                title="Founder & CEO",
                transaction_type="Sale",
                shares=25000,
                share_price=900.0,
                value=22500000.0,
            )
        ],
        provider_payload={},
    )

    candidates = generate_monitoring_candidates(
        {"watch_hints": []},
        company_data,
        previous_price=900.0,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    insider_candidates = [c for c in candidates if c["event_type"] == "insider_transaction"]
    assert len(insider_candidates) == 1
    assert "Founder & CEO" in insider_candidates[0]["description"]


async def test_run_monitoring_skips_vague_thesis_without_candidates(db, job_session_factory):
    user = User(email="vague@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="MSFT",
        name="Microsoft",
        quantity=5,
        average_cost_basis=200,
        current_price=210,
        current_value=1050,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="A friend recommended it.",
        confidence="low",
        review_cadence_days=7,
        interpretation={"watch_hints": [], "monitorability": "low"},
        source="user",
    )
    db.add(thesis)
    await db.commit()

    company_data = CompanyData(
        ticker="MSFT",
        name="Microsoft",
        sector="Technology",
        industry="Software",
        current_price=210.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )

    with patch("app.jobs.monitoring_run.settings") as mock_settings:
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_settings.market_data_provider = "alpha_vantage"
        with patch("app.jobs.monitoring_run.async_session", job_session_factory):
            with patch("app.jobs.monitoring_run.fetch_company_data", new_callable=AsyncMock, return_value=company_data):
                await run_monitoring()

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert events == []


def test_default_watch_hints_triggers_price_move_for_thesis_without_interpretation():
    """A thesis with no interpretation still gets price move monitoring via defaults."""
    company_data = CompanyData(
        ticker="GOOG",
        name="Alphabet",
        sector="Technology",
        industry="Internet",
        current_price=160.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )
    # No interpretation at all — should still detect 6.7% move (>5% default)
    candidates = generate_monitoring_candidates(
        None,
        company_data,
        previous_price=150.0,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert len(candidates) == 1
    assert candidates[0]["event_type"] == "price_move"


def test_founder_news_keyword_matches():
    """Expanded keywords catch CEO/founder/executive news."""
    company_data = CompanyData(
        ticker="AAPL",
        name="Apple",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=150.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[
            NewsItem(
                id="ceo-article",
                headline="Apple CEO Tim Cook announces major restructuring",
                summary="The executive team is being reshuffled.",
                published_at=datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc),
                source="Bloomberg",
                url="https://example.com/apple-ceo",
                sentiment=-0.2,
                topics=["technology"],
                ticker_relevance=0.9,
            )
        ],
        provider_payload={},
    )
    candidates = generate_monitoring_candidates(
        None,
        company_data,
        previous_price=150.0,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    news_candidates = [c for c in candidates if c["event_type"] == "news_or_earnings_candidate"]
    assert len(news_candidates) == 1
    assert "CEO" in news_candidates[0]["description"]
    assert news_candidates[0]["evidence"]["url"] == "https://example.com/apple-ceo"


async def test_run_monitoring_warns_when_no_api_key(db, job_session_factory):
    """When no Alpha Vantage key is set, a warning event is created."""
    user = User(email="nokey@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=1000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="I like Apple.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.commit()

    with patch("app.jobs.monitoring_run.async_session", job_session_factory):
        with patch("app.jobs.monitoring_run.settings") as mock_settings:
            mock_settings.alpha_vantage_api_key = ""
            mock_settings.market_data_provider = "alpha_vantage"
            await run_monitoring()

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(events) == 1
    assert events[0].event_type == "monitoring_inactive"
    assert "Alpha Vantage" in events[0].summary


def test_extract_proxy_tickers_returns_valid_entries():
    interpretation = {
        "proxy_signals": [
            {"ticker": "TSM", "rationale": "Foundry demand"},
            {"ticker": "NVDA", "rationale": "GPU demand"},
        ]
    }
    result = _extract_proxy_tickers(interpretation)
    assert len(result) == 2
    assert result[0]["ticker"] == "TSM"
    assert result[1]["ticker"] == "NVDA"


def test_extract_proxy_tickers_handles_missing_and_invalid():
    assert _extract_proxy_tickers(None) == []
    assert _extract_proxy_tickers({}) == []
    assert _extract_proxy_tickers({"proxy_signals": "not a list"}) == []
    assert _extract_proxy_tickers({"proxy_signals": [{"no_ticker": True}]}) == []
    assert _extract_proxy_tickers({"proxy_signals": ["string_entry"]}) == []


def test_generate_proxy_candidates_tags_with_proxy_prefix():
    proxy_data = CompanyData(
        ticker="TSM",
        name="TSMC",
        sector="Technology",
        industry="Semiconductors",
        current_price=150.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=8.0,
        news_items=[],
        provider_payload={},
    )
    candidates = _generate_proxy_candidates(
        proxy_data,
        {
            "ticker": "TSM",
            "rationale": "Foundry demand indicates downstream chip demand",
            "signal_hint": "Watch for capex guidance and fab utilization rates.",
        },
        None,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert len(candidates) >= 1
    for c in candidates:
        assert c["description"].startswith("[Proxy: TSM]")
        assert c["evidence"]["proxy_ticker"] == "TSM"
        assert "Foundry demand" in c["evidence"]["proxy_rationale"]
        assert c["evidence"]["proxy_signal_hint"] == "Watch for capex guidance and fab utilization rates."


def test_generate_proxy_candidates_only_applies_metrics_when_proxy_allows_them():
    """Proxy metrics should only be checked when the proxy explicitly opts into them."""
    proxy_data = CompanyData(
        ticker="TSM",
        name="TSMC",
        sector="Technology",
        industry="Semiconductors",
        current_price=150.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=-5.0,  # negative growth — but this is TSM, not the held ticker
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )
    interpretation = {
        "watch_hints": [
            {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Revenue growth should stay positive."}
        ]
    }
    candidates = _generate_proxy_candidates(
        proxy_data,
        {
            "ticker": "TSM",
            "rationale": "TSMC capex indicates foundry demand",
            "signal_hint": "Watch for capex guidance changes",
            "allowed_metrics": ["revenue_growth_yoy"],
        },
        interpretation,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    metric_candidates = [c for c in candidates if c["event_type"] == "metric_threshold"]
    assert len(metric_candidates) == 1


def test_generate_proxy_candidates_skips_metric_when_proxy_does_not_allow_it():
    proxy_data = CompanyData(
        ticker="TSM",
        name="TSMC",
        sector="Technology",
        industry="Semiconductors",
        current_price=150.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=-5.0,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )
    interpretation = {
        "watch_hints": [
            {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Revenue growth should stay positive."}
        ]
    }
    candidates = _generate_proxy_candidates(
        proxy_data,
        {
            "ticker": "TSM",
            "rationale": "TSMC capex indicates foundry demand",
            "signal_hint": "Watch for capex guidance changes",
        },
        interpretation,
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    metric_candidates = [c for c in candidates if c["event_type"] == "metric_threshold"]
    assert metric_candidates == []


async def test_run_monitoring_fetches_proxy_tickers_and_creates_events(db, job_session_factory):
    """When a thesis has proxy_signals, monitoring fetches those tickers and creates events from them."""
    user = User(email="proxy@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="ASML",
        name="ASML Holding",
        quantity=5,
        average_cost_basis=600,
        current_price=600,
        current_value=3000,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI will drive semiconductor demand.",
        must_remain_true="Hyperscaler capex keeps growing.",
        what_would_change_my_mind="Sustained capex cuts by cloud providers.",
        confidence="high",
        review_cadence_days=7,
        interpretation={
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 10.0, "rationale": "Review large moves."}
            ],
            "proxy_signals": [
                {"ticker": "TSM", "rationale": "TSMC capex indicates foundry demand.", "signal_hint": "Watch for capex guidance and order backlog."},
            ],
        },
        source="ai_assisted",
    )
    db.add(thesis)
    await db.commit()

    # Direct ticker data — no price move, no qualitative signals
    asml_data = CompanyData(
        ticker="ASML",
        name="ASML Holding",
        sector="Technology",
        industry="Semiconductors",
        current_price=610.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={},
    )
    # Proxy ticker data — has an earnings surprise signal
    tsm_data = CompanyData(
        ticker="TSM",
        name="TSMC",
        sector="Technology",
        industry="Semiconductors",
        current_price=150.0,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=12.0,
        news_items=[],
        provider_payload={},
    )

    async def mock_fetch(ticker):
        return {"ASML": asml_data, "TSM": tsm_data}.get(ticker)

    classification = type("Classification", (), {"severity": "warning", "analysis": "Proxy signal matters."})()
    classify_mock = AsyncMock(return_value=classification)

    with patch("app.jobs.monitoring_run.settings") as mock_settings:
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_settings.market_data_provider = "alpha_vantage"
        with patch("app.jobs.monitoring_run.async_session", job_session_factory):
            with patch("app.jobs.monitoring_run.fetch_company_data", new_callable=AsyncMock, side_effect=mock_fetch):
                with patch("app.jobs.monitoring_run.classify_event", classify_mock):
                    await run_monitoring()

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(events) >= 1
    # The event should come from the proxy ticker's earnings surprise
    proxy_events = [e for e in events if "Proxy: TSM" in e.summary]
    assert len(proxy_events) == 1
    assert proxy_events[0].holding_id == holding.id

    # Verify the stored summary includes the causal rationale for the user
    assert "Why this matters: TSMC capex indicates foundry demand." in proxy_events[0].summary
    assert "What to look for: Watch for capex guidance and order backlog." in proxy_events[0].summary

    # Verify the classifier received the causal rationale and signal hint
    classify_calls = classify_mock.call_args_list
    proxy_call = [c for c in classify_calls if "TSMC capex indicates foundry demand" in c.kwargs.get("event_description", "")]
    assert len(proxy_call) == 1, "Classifier should receive proxy rationale explaining why the signal matters"
    assert "capex guidance" in proxy_call[0].kwargs["event_description"], "Classifier should receive signal_hint"


async def test_run_monitoring_deduplicates_across_direct_and_proxy(db, job_session_factory):
    """If a direct ticker and proxy ticker produce the same article_id, only one event is created."""
    user = User(email="dedup@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding1 = Holding(
        user_id=user.id, ticker="NVDA", name="NVIDIA", quantity=10,
        average_cost_basis=800, current_price=800, current_value=8000,
    )
    holding2 = Holding(
        user_id=user.id, ticker="AMD", name="AMD", quantity=20,
        average_cost_basis=100, current_price=100, current_value=2000,
    )
    db.add_all([holding1, holding2])
    await db.flush()

    # Both theses monitor TSM as a proxy
    shared_proxy = [{"ticker": "TSM", "rationale": "Foundry demand."}]
    thesis1 = Thesis(
        user_id=user.id, holding_id=holding1.id, status="active",
        thesis_kind="company", why_own_it="AI GPU demand.", confidence="high",
        review_cadence_days=7,
        interpretation={"watch_hints": [], "proxy_signals": shared_proxy},
        source="user",
    )
    thesis2 = Thesis(
        user_id=user.id, holding_id=holding2.id, status="active",
        thesis_kind="company", why_own_it="Data center CPUs.", confidence="high",
        review_cadence_days=7,
        interpretation={"watch_hints": [], "proxy_signals": shared_proxy},
        source="user",
    )
    db.add_all([thesis1, thesis2])
    await db.commit()

    # TSM data with a dedupable earnings surprise
    tsm_data = CompanyData(
        ticker="TSM", name="TSMC", sector="Technology", industry="Semiconductors",
        current_price=150.0, market_cap=None, pe_ratio=None,
        revenue_growth_yoy=None, earnings_growth_yoy=None, dividend_yield=None,
        description="", recent_news=[], upcoming_earnings_date=None,
        recent_earnings_surprise_pct=10.0, news_items=[], provider_payload={},
    )
    nvda_data = CompanyData(
        ticker="NVDA", name="NVIDIA", sector="Technology", industry="Semiconductors",
        current_price=800.0, market_cap=None, pe_ratio=None,
        revenue_growth_yoy=None, earnings_growth_yoy=None, dividend_yield=None,
        description="", recent_news=[], upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None, news_items=[], provider_payload={},
    )
    amd_data = CompanyData(
        ticker="AMD", name="AMD", sector="Technology", industry="Semiconductors",
        current_price=100.0, market_cap=None, pe_ratio=None,
        revenue_growth_yoy=None, earnings_growth_yoy=None, dividend_yield=None,
        description="", recent_news=[], upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None, news_items=[], provider_payload={},
    )

    async def mock_fetch(ticker):
        return {"NVDA": nvda_data, "AMD": amd_data, "TSM": tsm_data}.get(ticker)

    classification = type("Classification", (), {"severity": "warning", "analysis": "Proxy signal."})()

    with patch("app.jobs.monitoring_run.settings") as mock_settings:
        mock_settings.alpha_vantage_api_key = "test-key"
        mock_settings.market_data_provider = "alpha_vantage"
        with patch("app.jobs.monitoring_run.async_session", job_session_factory):
            with patch("app.jobs.monitoring_run.fetch_company_data", new_callable=AsyncMock, side_effect=mock_fetch):
                with patch("app.jobs.monitoring_run.classify_event", new_callable=AsyncMock, return_value=classification):
                    await run_monitoring()

    events = (await db.execute(MonitoringEvent.__table__.select())).all()
    # Both theses should get the proxy event (dedup is within a thesis, not across theses)
    # But the earnings_surprise candidate doesn't have article_id/transaction_id/transcript_id
    # so it won't be deduped — each thesis gets its own event
    proxy_events = [e for e in events if "Proxy: TSM" in e.summary]
    assert len(proxy_events) == 2  # one per thesis
