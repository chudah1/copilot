from datetime import datetime, timedelta, timezone

import pytest

from app.services.market_data import _TTLCache, QUALITATIVE_KEYWORDS
from app.services.market_data import (
    _build_news_candidate,
    _build_company_data_from_alpha_vantage,
    _fetch_alpha_vantage_transcript_payloads,
    _fallback_transcript_quarters,
    _merge_company_data,
    CompanyData,
    fetch_company_data,
    _parse_alpha_vantage_earnings,
    _parse_alpha_vantage_earnings_calendar,
    _parse_alpha_vantage_insider_transactions,
    _parse_alpha_vantage_news,
    _parse_alpha_vantage_overview,
    _parse_alpha_vantage_quote,
    _parse_alpha_vantage_transcript,
    transcript_fetch_diagnostics,
    is_current_earnings_call,
    shortlist_qualitative_candidates,
)


def test_parse_alpha_vantage_quote():
    payload = {"Global Quote": {"05. price": "172.45"}}
    assert _parse_alpha_vantage_quote(payload) == 172.45


def test_parse_alpha_vantage_overview():
    payload = {
        "Name": "Apple Inc",
        "Sector": "Technology",
        "Industry": "Consumer Electronics",
        "Description": "Makes devices",
        "MarketCapitalization": "2500000000000",
        "PERatio": "28.5",
        "DividendYield": "0.0045",
        "QuarterlyRevenueGrowthYOY": "0.08",
        "QuarterlyEarningsGrowthYOY": "0.12",
    }
    overview = _parse_alpha_vantage_overview(payload)
    assert overview["name"] == "Apple Inc"
    assert overview["sector"] == "Technology"
    assert overview["market_cap"] == 2500000000000.0
    assert overview["pe_ratio"] == 28.5
    assert overview["revenue_growth_yoy"] == 0.08


def test_parse_alpha_vantage_earnings():
    payload = {
        "quarterlyEarnings": [
            {
                "reportedDate": "2026-05-01",
                "fiscalDateEnding": "2026-03-31",
                "surprisePercentage": "7.25",
            }
        ]
    }
    earnings = _parse_alpha_vantage_earnings(payload)
    assert earnings["recent_earnings_surprise_pct"] == 7.25
    assert earnings["recent_reported_at"] == datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert earnings["recent_fiscal_quarter"] == "2026Q1"
    assert earnings["recent_fiscal_quarters"] == ["2026Q1"]


def test_parse_alpha_vantage_earnings_includes_multiple_recent_quarters():
    payload = {
        "quarterlyEarnings": [
            {
                "reportedDate": "2026-05-01",
                "fiscalDateEnding": "2026-03-31",
                "surprisePercentage": "7.25",
            },
                    {
                        "reportedDate": "2026-03-01",
                        "fiscalDateEnding": "2025-12-31",
                        "surprisePercentage": "5.10",
                    },
            {
                "reportedDate": "2025-11-01",
                "fiscalDateEnding": "2025-09-30",
                "surprisePercentage": "3.80",
            },
        ]
    }

    earnings = _parse_alpha_vantage_earnings(payload)
    assert earnings["recent_fiscal_quarters"] == ["2026Q1", "2025Q4"]


def test_parse_alpha_vantage_earnings_calendar():
    payload = "symbol,name,reportDate,fiscalDateEnding,estimate,currency\nAAPL,Apple Inc,2026-05-16,2026-03-31,1.20,USD"
    assert _parse_alpha_vantage_earnings_calendar(payload, "AAPL") == datetime(2026, 5, 16, tzinfo=timezone.utc)


def test_parse_alpha_vantage_news():
    payload = {
        "feed": [
            {
                "title": "Apple issues new guidance",
                "summary": "Management updated forward expectations.",
                "time_published": "20260510T1200",
                "source": "Reuters",
                "url": "https://example.com/apple",
                "overall_sentiment_score": "0.18",
                "topics": [{"topic": "earnings"}],
                "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.55"}],
            }
        ]
    }
    items = _parse_alpha_vantage_news(payload, "AAPL")
    assert len(items) == 1
    assert items[0].headline == "Apple issues new guidance"
    assert items[0].ticker_relevance == 0.55
    assert items[0].topics == ["earnings"]


def test_parse_alpha_vantage_transcript():
    payload = {
        "symbol": "AAPL",
        "quarter": "2026Q1",
        "date": "2026-05-01",
        "overall_sentiment_score": "-0.22",
        "overall_sentiment_label": "Negative",
        "transcript": [
            {"speaker": "CEO", "content": "We are seeing some demand headwinds in China."},
            {"speaker": "CFO", "content": "Gross margins will be pressured next quarter."},
        ],
    }
    transcript = _parse_alpha_vantage_transcript(payload)
    assert transcript is not None
    assert transcript.quarter == "2026Q1"
    assert transcript.sentiment == -0.22
    assert transcript.sentiment_label == "Negative"
    assert any("demand headwinds" in highlight.lower() for highlight in transcript.highlights)


def test_is_current_earnings_call_rejects_stale_dated_transcript():
    transcript = _parse_alpha_vantage_transcript(
        {
            "quarter": "2026Q1",
            "date": "2026-01-30",
            "overall_sentiment_score": "-0.22",
            "overall_sentiment_label": "Negative",
            "transcript": [{"speaker": "CEO", "content": "We are seeing some demand headwinds in China."}],
        }
    )

    assert transcript is not None
    assert is_current_earnings_call(
        transcript,
        now=datetime(2026, 6, 6, tzinfo=timezone.utc),
        recent_fiscal_quarter="2026Q2",
    ) is False


def test_build_company_data_drops_stale_transcript_from_live_payload():
    data = _build_company_data_from_alpha_vantage(
        "AAPL",
        {
            "quote": {"Global Quote": {"05. price": "210.15"}},
            "overview": {
                "Name": "Apple Inc",
                "Sector": "Technology",
                "Industry": "Consumer Electronics",
                "Description": "Makes devices",
                "MarketCapitalization": "4500000000000",
                "PERatio": "37.2",
                "QuarterlyRevenueGrowthYOY": "0.17",
                "QuarterlyEarningsGrowthYOY": "0.22",
            },
            "earnings": {
                "quarterlyEarnings": [
                    {
                        "reportedDate": "2026-05-01",
                        "fiscalDateEnding": "2026-03-31",
                        "surprisePercentage": "4.5",
                    }
                ]
            },
            "earnings_calendar": "",
            "news": {"feed": []},
            "earnings_call_transcript": {
                "quarter": "2026Q1",
                "date": "2026-01-30",
                "overall_sentiment_score": "-0.22",
                "overall_sentiment_label": "Negative",
                "transcript": "Services demand was solid but China was softer.",
            },
            "insider_transactions": {"data": []},
        },
    )

    assert data.recent_fiscal_quarter == "2026Q1"
    assert data.earnings_call is None


def test_build_company_data_keeps_multiple_current_transcripts():
    # Reference dates relative to today so the assertion doesn't age out — the
    # 120-day currency window pushes fixed-date fixtures out of "current" as
    # calendar time moves on. Choose spans that fall into two distinct calendar
    # quarters so multi-quarter behavior is exercised regardless of when the
    # test runs.
    now = datetime.now(timezone.utc)
    recent_dt = now - timedelta(days=30)
    prior_dt = now - timedelta(days=100)
    recent_call = recent_dt.date().isoformat()
    prior_call = prior_dt.date().isoformat()

    def _q(dt: datetime) -> str:
        return f"{dt.year}Q{((dt.month - 1) // 3) + 1}"

    recent_quarter = _q(recent_dt)
    prior_quarter = _q(prior_dt)
    if recent_quarter == prior_quarter:
        # Nudge prior_dt further back until it crosses a quarter boundary.
        prior_dt = now - timedelta(days=115)
        prior_call = prior_dt.date().isoformat()
        prior_quarter = _q(prior_dt)
    data = _build_company_data_from_alpha_vantage(
        "AAPL",
        {
            "quote": {"Global Quote": {"05. price": "210.15"}},
            "overview": {
                "Name": "Apple Inc",
                "Sector": "Technology",
                "Industry": "Consumer Electronics",
                "Description": "Makes devices",
                "MarketCapitalization": "4500000000000",
                "PERatio": "37.2",
                "QuarterlyRevenueGrowthYOY": "0.17",
                "QuarterlyEarningsGrowthYOY": "0.22",
            },
            "earnings": {
                "quarterlyEarnings": [
                    {
                        "reportedDate": recent_call,
                        "fiscalDateEnding": recent_call,
                        "surprisePercentage": "4.5",
                    },
                    {
                        "reportedDate": prior_call,
                        "fiscalDateEnding": prior_call,
                        "surprisePercentage": "5.1",
                    },
                ]
            },
            "earnings_calendar": "",
            "news": {"feed": []},
            "earnings_call_transcripts": [
                {
                    "quarter": recent_quarter,
                    "date": recent_call,
                    "transcript": "Services demand was solid and margins improved.",
                },
                {
                    "quarter": prior_quarter,
                    "date": prior_call,
                    "transcript": "Product demand improved and channel inventory normalized.",
                },
            ],
            "insider_transactions": {"data": []},
        },
    )

    assert data.recent_fiscal_quarters == [recent_quarter, prior_quarter]
    assert data.earnings_call is not None
    assert data.earnings_call.quarter == recent_quarter
    assert [transcript.quarter for transcript in data.earnings_calls] == [recent_quarter, prior_quarter]


def test_merge_company_data_preserves_transcript_enrichment():
    base = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=210.15,
        market_cap=4500000000000.0,
        pe_ratio=37.2,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="Makes devices",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={"provider": "yfinance"},
        recent_fiscal_quarter="2026Q1",
        recent_fiscal_quarters=["2026Q1"],
        earnings_call=None,
        earnings_calls=[],
        insider_transactions=[],
        country="United States",
        currency="USD",
    )
    transcript = _parse_alpha_vantage_transcript(
        {
            "quarter": "2026Q1",
            "date": "2026-05-01",
            "transcript": "Services demand was solid and margins improved.",
        }
    )
    enrichment = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Unknown",
        industry="Unknown",
        current_price=None,
        market_cap=None,
        pe_ratio=None,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=4.5,
        news_items=[],
        provider_payload={"provider": "alpha_vantage"},
        recent_fiscal_quarter="2026Q1",
        recent_fiscal_quarters=["2026Q1"],
        earnings_call=transcript,
        earnings_calls=[transcript] if transcript else [],
        insider_transactions=[],
        country="Unknown",
        currency=None,
    )

    merged = _merge_company_data(base, enrichment)

    assert merged.current_price == 210.15
    assert merged.earnings_call is not None
    assert merged.earnings_call.quarter == "2026Q1"
    assert merged.provider_payload["baseline_provider"] == "yfinance"
    assert merged.provider_payload["enrichment_provider"] == "alpha_vantage"


@pytest.mark.asyncio
async def test_fetch_company_data_merges_partial_alpha_vantage_with_yfinance(monkeypatch):
    monkeypatch.setattr("app.services.market_data.settings.market_data_provider", "alpha_vantage", raising=False)
    monkeypatch.setattr("app.services.market_data.settings.alpha_vantage_api_key", "test-key", raising=False)

    transcript = {
        "quarter": "2026Q1",
        "date": "2026-05-01",
        "transcript": "Services demand was solid and margins improved.",
    }
    partial_payload = {
        "quote": {},
        "overview": {},
        "earnings": {
            "quarterlyEarnings": [
                {
                    "reportedDate": "2026-05-01",
                    "fiscalDateEnding": "2026-03-31",
                    "surprisePercentage": "4.5",
                }
            ]
        },
        "earnings_calendar": "",
        "news": {"feed": []},
        "earnings_call_transcripts": [transcript],
        "insider_transactions": {"data": []},
    }
    yfinance_data = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=210.15,
        market_cap=4500000000000.0,
        pe_ratio=37.2,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="Makes devices",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={"provider": "yfinance"},
        recent_fiscal_quarter="2026Q1",
        recent_fiscal_quarters=["2026Q1"],
        earnings_call=None,
        earnings_calls=[],
        insider_transactions=[],
        country="United States",
        currency="USD",
    )

    async def fake_payloads(_ticker: str):
        return partial_payload

    async def fake_yfinance(_ticker: str):
        return yfinance_data

    monkeypatch.setattr("app.services.market_data._fetch_alpha_vantage_payloads", fake_payloads)
    monkeypatch.setattr("app.services.market_data._fetch_yfinance_company_data", fake_yfinance)

    data = await fetch_company_data("AAPL")

    assert data is not None
    assert data.current_price == 210.15
    assert data.earnings_call is not None
    assert data.earnings_call.quarter == "2026Q1"


def test_transcript_fetch_diagnostics_reads_alpha_vantage_payload():
    data = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=210.15,
        market_cap=4500000000000.0,
        pe_ratio=37.2,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="Makes devices",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={
            "provider": "yfinance",
            "alpha_vantage": {
                "transcript_diagnostics": {
                    "requested_quarters": ["2026Q1"],
                    "returned_quarters": [],
                    "empty_quarters": ["2026Q1"],
                    "error_quarters": {},
                }
            },
        },
        recent_fiscal_quarter="2026Q1",
        recent_fiscal_quarters=["2026Q1"],
        earnings_call=None,
        earnings_calls=[],
        insider_transactions=[],
        country="United States",
        currency="USD",
    )

    diagnostics = transcript_fetch_diagnostics(data)

    assert diagnostics["requested_quarters"] == ["2026Q1"]
    assert diagnostics["empty_quarters"] == ["2026Q1"]
    assert diagnostics["available_transcripts"] == 0


def test_parse_transcript_backfills_call_date_from_quarter_when_missing():
    # Alpha Vantage's EARNINGS_CALL_TRANSCRIPT response frequently omits the
    # date field. Without a back-filled call_date, is_current_earnings_call
    # returns False for genuinely fresh transcripts and the pipeline drops
    # them silently. The quarter-end proxy keeps recent quarters current.
    payload = {"quarter": "2026Q2", "symbol": "AAPL", "transcript": "…real content…"}
    transcript = _parse_alpha_vantage_transcript(payload)
    assert transcript is not None
    assert transcript.call_date == datetime(2026, 6, 30, tzinfo=timezone.utc)
    # And the fresh-enough check accepts it.
    assert is_current_earnings_call(
        transcript,
        now=datetime(2026, 7, 5, tzinfo=timezone.utc),
    )


def test_fallback_transcript_quarters_uses_recent_calendar_quarters():
    # June 26 is still inside calendar Q2 2026 (Q2 ends June 30). The most
    # recently completed quarter is Q1 2026, so the fallback should lead
    # with Q1 rather than the current-quarter Q2, which no company can have
    # reported on yet.
    quarters = _fallback_transcript_quarters(
        reference_now=datetime(2026, 6, 26, tzinfo=timezone.utc),
        count=3,
    )

    assert quarters == ["2026Q1", "2025Q4", "2025Q3"]


def test_fallback_transcript_quarters_wraps_year_boundary():
    # Early January is inside calendar Q1; the last completed quarter is the
    # prior year's Q4. Verifies the year-decrement path.
    quarters = _fallback_transcript_quarters(
        reference_now=datetime(2026, 1, 10, tzinfo=timezone.utc),
        count=2,
    )

    assert quarters == ["2025Q4", "2025Q3"]


@pytest.mark.asyncio
async def test_fetch_company_data_uses_yfinance_quarter_for_transcript_retry(monkeypatch):
    monkeypatch.setattr("app.services.market_data.settings.market_data_provider", "alpha_vantage", raising=False)
    monkeypatch.setattr("app.services.market_data.settings.alpha_vantage_api_key", "test-key", raising=False)

    partial_payload = {
        "quote": {},
        "overview": {},
        "earnings": {},
        "earnings_calendar": "",
        "news": {"feed": []},
        "earnings_call_transcripts": [],
        "insider_transactions": {"data": []},
    }
    yfinance_data = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=210.15,
        market_cap=4500000000000.0,
        pe_ratio=37.2,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="Makes devices",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={"provider": "yfinance"},
        recent_fiscal_quarter="2026Q1",
        recent_fiscal_quarters=["2026Q1"],
        earnings_call=None,
        earnings_calls=[],
        insider_transactions=[],
        country="United States",
        currency="USD",
    )

    async def fake_payloads(_ticker: str):
        return partial_payload

    async def fake_yfinance(_ticker: str):
        return yfinance_data

    async def fake_transcripts(_ticker: str, quarters: list[str], **_kwargs):
        assert quarters == ["2026Q1"]
        return [
            {
                "quarter": "2026Q1",
                "date": "2026-05-01",
                "transcript": "Services demand was solid and margins improved.",
            }
        ]

    monkeypatch.setattr("app.services.market_data._fetch_alpha_vantage_payloads", fake_payloads)
    monkeypatch.setattr("app.services.market_data._fetch_yfinance_company_data", fake_yfinance)
    monkeypatch.setattr("app.services.market_data._fetch_alpha_vantage_transcript_payloads", fake_transcripts)

    data = await fetch_company_data("AAPL")

    assert data is not None
    assert data.earnings_call is not None
    assert data.earnings_call.quarter == "2026Q1"


@pytest.mark.asyncio
async def test_fetch_alpha_vantage_transcript_payloads_marks_rate_limit_as_error(monkeypatch):
    monkeypatch.setattr("app.services.market_data.settings.alpha_vantage_api_key", "test-key", raising=False)

    async def fake_cached_request(_client, _function, _ttl, **kwargs):
        if kwargs["quarter"] == "2026Q2":
            return {"Note": "Please consider spreading out your free API requests more sparingly."}
        return {
            "quarter": "2026Q1",
            "date": "2026-05-01",
            "transcript": "Demand stayed strong and margins improved.",
        }

    monkeypatch.setattr("app.services.market_data._cached_request", fake_cached_request)

    payloads, diagnostics = await _fetch_alpha_vantage_transcript_payloads("MSFT", ["2026Q2", "2026Q1"])

    assert len(payloads) == 1
    assert diagnostics["returned_quarters"] == ["2026Q1"]
    assert diagnostics["error_quarters"]["2026Q2"].startswith("Please consider spreading out")


@pytest.mark.asyncio
async def test_fetch_company_data_uses_calendar_fallback_for_transcript_retry(monkeypatch):
    monkeypatch.setattr("app.services.market_data.settings.market_data_provider", "alpha_vantage", raising=False)
    monkeypatch.setattr("app.services.market_data.settings.alpha_vantage_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        "app.services.market_data._fallback_transcript_quarters",
        lambda **_kwargs: ["2026Q2", "2026Q1"],
    )

    partial_payload = {
        "quote": {},
        "overview": {},
        "earnings": {},
        "earnings_calendar": "",
        "news": {"feed": []},
        "earnings_call_transcripts": [],
        "insider_transactions": {"data": []},
    }
    yfinance_data = CompanyData(
        ticker="AAPL",
        name="Apple Inc",
        sector="Technology",
        industry="Consumer Electronics",
        current_price=210.15,
        market_cap=4500000000000.0,
        pe_ratio=37.2,
        revenue_growth_yoy=None,
        earnings_growth_yoy=None,
        dividend_yield=None,
        description="Makes devices",
        recent_news=[],
        upcoming_earnings_date=None,
        recent_earnings_surprise_pct=None,
        news_items=[],
        provider_payload={"provider": "yfinance"},
        recent_fiscal_quarter=None,
        recent_fiscal_quarters=[],
        earnings_call=None,
        earnings_calls=[],
        insider_transactions=[],
        country="United States",
        currency="USD",
    )

    async def fake_payloads(_ticker: str):
        return partial_payload

    async def fake_yfinance(_ticker: str):
        return yfinance_data

    async def fake_transcripts(_ticker: str, quarters: list[str], **_kwargs):
        assert quarters == ["2026Q2", "2026Q1"]
        return [
            {
                "quarter": "2026Q1",
                "date": "2026-05-01",
                "transcript": "Services demand was solid and margins improved.",
            }
        ]

    monkeypatch.setattr("app.services.market_data._fetch_alpha_vantage_payloads", fake_payloads)
    monkeypatch.setattr("app.services.market_data._fetch_yfinance_company_data", fake_yfinance)
    monkeypatch.setattr("app.services.market_data._fetch_alpha_vantage_transcript_payloads", fake_transcripts)

    data = await fetch_company_data("AAPL")

    assert data is not None
    assert data.earnings_call is not None
    assert data.earnings_call.quarter == "2026Q1"
    diagnostics = transcript_fetch_diagnostics(data)
    assert diagnostics["requested_quarters"] == ["2026Q2", "2026Q1"]
    assert diagnostics["quarter_strategy"] == "calendar_fallback"


def test_parse_alpha_vantage_insider_transactions():
    payload = {
        "data": [
            {
                "transactionDate": "2026-05-09",
                "filingDate": "2026-05-10",
                "insiderName": "Jane Founder",
                "officerTitle": "Founder & CEO",
                "transactionType": "Sale",
                "shareCount": "15000",
                "sharePrice": "182.4",
            }
        ]
    }
    transactions = _parse_alpha_vantage_insider_transactions(payload)
    assert len(transactions) == 1
    assert transactions[0].insider_name == "Jane Founder"
    assert transactions[0].title == "Founder & CEO"
    assert transactions[0].transaction_type == "Sale"
    assert transactions[0].value == 2736000.0


def test_shortlist_qualitative_candidates_filters_noise():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "Apple issues new guidance",
                    "summary": "Management updated forward expectations.",
                    "time_published": "20260511T0900",
                    "source": "Reuters",
                    "url": "https://example.com/apple-guidance",
                    "overall_sentiment_score": "0.18",
                    "topics": [{"topic": "earnings"}],
                    "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.55"}],
                },
                {
                    "title": "Apple opens new store",
                    "summary": "Retail expansion continues.",
                    "time_published": "20260509T0900",
                    "source": "Reuters",
                    "url": "https://example.com/apple-store",
                    "overall_sentiment_score": "0.10",
                    "topics": [{"topic": "retail_wholesale"}],
                    "ticker_sentiment": [{"ticker": "AAPL", "relevance_score": "0.55"}],
                },
            ]
        },
        "AAPL",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=6.0,
        upcoming_earnings_date=now + timedelta(days=3),
        now=now,
    )
    assert len(candidates) == 3
    assert candidates[0]["event_type"] == "earnings_surprise"
    assert candidates[1]["event_type"] == "upcoming_earnings"
    assert candidates[2]["event_type"] == "news_or_earnings_candidate"
    # Description must spell out the direction — a +6% beat read as ambiguous
    # by downstream LLM classifiers (especially the gpt-4o-mini fallback) and
    # routinely got misclassified as a "potential miss". The walkthrough on
    # 2026-06-14 surfaced this end-to-end.
    assert "beat" in candidates[0]["description"].lower()
    assert "6.0%" in candidates[0]["description"]


def test_earnings_surprise_candidate_describes_misses_explicitly():
    """Negative surprises must call out the miss, not just a signed number."""
    from app.services.market_data import _build_earnings_surprise_candidate

    miss = _build_earnings_surprise_candidate(-7.5)
    assert miss is not None
    desc = miss["description"].lower()
    assert "miss" in desc
    assert "7.5%" in desc
    # Sign already consumed by the wording; the raw evidence keeps the signed value.
    assert "-" not in desc.replace("\n", " ")
    assert miss["evidence"]["recent_earnings_surprise_pct"] == -7.5


def test_earnings_surprise_candidate_describes_beats_explicitly():
    """Positive surprises must call out the beat to remove classifier ambiguity."""
    from app.services.market_data import _build_earnings_surprise_candidate

    beat = _build_earnings_surprise_candidate(5.6)
    assert beat is not None
    desc = beat["description"].lower()
    assert "beat" in desc
    assert "5.6%" in desc
    assert beat["evidence"]["recent_earnings_surprise_pct"] == 5.6


def test_earnings_surprise_candidate_drops_below_threshold():
    """Surprises within +/- 5% are noise — the existing 5%-threshold filter
    stays in place; verify the new wording doesn't accidentally remove it."""
    from app.services.market_data import _build_earnings_surprise_candidate

    assert _build_earnings_surprise_candidate(None) is None
    assert _build_earnings_surprise_candidate(4.9) is None
    assert _build_earnings_surprise_candidate(-4.9) is None
    # Boundary: filter is `abs(x) < 5`, so exactly 5.0 surfaces a candidate.
    assert _build_earnings_surprise_candidate(5.0) is not None
    assert _build_earnings_surprise_candidate(5.1) is not None


def test_shortlist_qualitative_candidates_marks_product_ramp_updates():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "NVIDIA says Blackwell rollout is ahead of plan",
                    "summary": "Management said Blackwell deployment is accelerating and supply is improving.",
                    "time_published": "20260511T0900",
                    "source": "Reuters",
                    "url": "https://example.com/nvda-blackwell",
                    "overall_sentiment_score": "0.18",
                    "topics": [{"topic": "earnings"}],
                    "ticker_sentiment": [{"ticker": "NVDA", "relevance_score": "0.55"}],
                }
            ]
        },
        "NVDA",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="NVDA",
    )
    assert len(candidates) == 1
    assert candidates[0]["event_type"] == "product_ramp_update"


def test_shortlist_qualitative_candidates_marks_contract_renewal_updates():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "Oracle says large customer renewals and backlog remain strong",
                    "summary": "Management highlighted contract extensions and remaining performance obligations growth.",
                    "time_published": "20260511T0900",
                    "source": "Reuters",
                    "url": "https://example.com/orcl-renewals",
                    "overall_sentiment_score": "0.12",
                    "topics": [{"topic": "earnings"}],
                    "ticker_sentiment": [{"ticker": "ORCL", "relevance_score": "0.55"}],
                }
            ]
        },
        "ORCL",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="ORCL",
    )
    assert len(candidates) == 1
    assert candidates[0]["event_type"] == "contract_renewal_update"
    assert "backlog" in candidates[0]["evidence"]["topic_context"]


def test_shortlist_qualitative_candidates_drops_roundup_noise():
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "Why Intel, AMD, Arm, and Other Artificial Intelligence (AI) Stocks Popped Today",
                    "summary": "A broad sector roundup discussing several chip stocks and the AI trade.",
                    "time_published": "20260613T0900",
                    "source": "Motley Fool",
                    "url": "https://example.com/amd-roundup",
                    "overall_sentiment_score": "0.12",
                    "topics": [{"topic": "technology"}],
                    "ticker_sentiment": [{"ticker": "AMD", "relevance_score": "0.55"}],
                }
            ]
        },
        "AMD",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="AMD",
    )
    assert candidates == []


def test_shortlist_qualitative_candidates_drops_low_relevance_generic_mentions():
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "Chip stocks trade mixed as AI optimism cools",
                    "summary": "AMD was mentioned alongside other peers in a broad sector wrap.",
                    "time_published": "20260613T0900",
                    "source": "Reuters",
                    "url": "https://example.com/chip-wrap",
                    "overall_sentiment_score": "0.02",
                    "topics": [{"topic": "technology"}],
                    "ticker_sentiment": [{"ticker": "AMD", "relevance_score": "0.20"}],
                }
            ]
        },
        "AMD",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="AMD",
    )
    assert candidates == []


def test_shortlist_qualitative_candidates_drops_articles_where_target_is_not_primary_ticker():
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "NVIDIA Corporation $NVDA Position Cut by ROI Financial Advisors LLC",
                    "summary": "ROI Financial Advisors reduced its NVIDIA stake after strong quarterly results.",
                    "time_published": "20260613T0944",
                    "source": "MarketBeat",
                    "url": "https://example.com/nvda-position-cut",
                    "overall_sentiment_score": "0.05",
                    "topics": [{"topic": "financial_markets"}],
                    "ticker_sentiment": [
                        {"ticker": "NVDA", "relevance_score": "0.75"},
                        {"ticker": "AMD", "relevance_score": "0.20"},
                    ],
                }
            ]
        },
        "AMD",
    )

    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="AMD",
    )

    assert candidates == []


def test_build_news_candidate_does_not_match_rpo_inside_corporation():
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "NVIDIA Corporation $NVDA Position Cut by ROI Financial Advisors LLC",
                    "summary": "ROI Financial Advisors reduced its stake in NVIDIA after strong quarterly results.",
                    "time_published": "20260613T0944",
                    "source": "MarketBeat",
                    "url": "https://example.com/nvda-position-cut",
                    "overall_sentiment_score": "0.05",
                    "topics": [{"topic": "earnings"}],
                    "ticker_sentiment": [{"ticker": "NVDA", "relevance_score": "0.75"}],
                }
            ]
        },
        "NVDA",
    )

    candidate = _build_news_candidate(items[0], now=now, ticker="NVDA")

    assert candidate is not None
    assert candidate[1]["event_type"] == "news_or_earnings_candidate"
    assert candidate[1]["evidence"]["matched_topics"] == []


def test_shortlist_qualitative_candidates_marks_funding_updates():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    items = _parse_alpha_vantage_news(
        {
            "feed": [
                {
                    "title": "Affirm expands warehouse facility as ABS market stays open",
                    "summary": "Funding capacity improved and management said securitization costs remain stable.",
                    "time_published": "20260511T0900",
                    "source": "Reuters",
                    "url": "https://example.com/afrm-funding",
                    "overall_sentiment_score": "0.14",
                    "topics": [{"topic": "finance"}],
                    "ticker_sentiment": [{"ticker": "AFRM", "relevance_score": "0.55"}],
                }
            ]
        },
        "AFRM",
    )
    candidates = shortlist_qualitative_candidates(
        items,
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        now=now,
        ticker="AFRM",
    )
    assert len(candidates) == 1
    assert candidates[0]["event_type"] == "funding_condition_update"
    assert "funding capacity" in candidates[0]["evidence"]["topic_context"]


def test_shortlist_qualitative_candidates_includes_transcript_and_insider_signals():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    transcript = _parse_alpha_vantage_transcript(
        {
            "quarter": "2026Q1",
            "date": "2026-05-05",
            "overall_sentiment_score": "-0.21",
            "overall_sentiment_label": "Negative",
            "transcript": "Management discussed demand slowdown and margin pressure in the quarter.",
        }
    )
    insiders = _parse_alpha_vantage_insider_transactions(
        {
            "data": [
                {
                    "transactionDate": "2026-05-10",
                    "filingDate": "2026-05-10",
                    "insiderName": "Jane Founder",
                    "officerTitle": "Founder & CEO",
                    "transactionType": "Sale",
                    "shareCount": "5000",
                    "sharePrice": "100.0",
                }
            ]
        }
    )
    candidates = shortlist_qualitative_candidates(
        [],
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        earnings_call=transcript,
        insider_transactions=insiders,
        now=now,
    )
    event_types = [candidate["event_type"] for candidate in candidates]
    assert "earnings_call_transcript" in event_types
    assert "insider_transaction" in event_types


def test_shortlist_qualitative_candidates_includes_multiple_transcripts():
    now = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)
    transcript_one = _parse_alpha_vantage_transcript(
        {
            "quarter": "2026Q1",
            "date": "2026-05-05",
            "transcript": "Management said data center demand remained strong.",
        }
    )
    transcript_two = _parse_alpha_vantage_transcript(
        {
            "quarter": "2025Q4",
            "date": "2026-03-01",
            "transcript": "Management said gaming demand improved and inventory normalized.",
        }
    )

    candidates = shortlist_qualitative_candidates(
        [],
        recent_earnings_surprise_pct=None,
        upcoming_earnings_date=None,
        earnings_calls=[transcript_one, transcript_two],
        now=now,
        transcript_max_age_days=120,
    )

    transcript_candidates = [candidate for candidate in candidates if candidate["event_type"] == "earnings_call_transcript"]
    assert len(transcript_candidates) == 2


def test_ttl_cache_stores_and_expires():
    cache = _TTLCache()
    cache.set("key1", {"data": 42}, ttl=10)
    assert cache.get("key1") == {"data": 42}

    # Manually expire
    cache._store["key1"].expires_at = 0
    assert cache.get("key1") is None


def test_ttl_cache_clear():
    cache = _TTLCache()
    cache.set("a", 1, ttl=10)
    cache.set("b", 2, ttl=10)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_expanded_keywords_include_founder_and_executive_terms():
    expected = {"ceo", "founder", "executive", "resign", "appoint", "cfo", "coo"}
    assert expected.issubset(set(QUALITATIVE_KEYWORDS))


def test_analyst_revision_candidate_fires_on_net_downgrades():
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from app.services.market_data import _fetch_analyst_consensus_sync

    mock_ticker = MagicMock()
    mock_ticker.recommendations = pd.DataFrame({
        "period": ["0m", "-1m", "-2m"],
        "strongBuy": [1, 2, 3],
        "buy": [2, 3, 3],
        "hold": [5, 4, 4],
        "sell": [4, 2, 1],
        "strongSell": [3, 1, 0],
    })
    mock_ticker.analyst_price_targets = {
        "current": 100.0,
        "mean": 90.0,
        "low": 70.0,
        "high": 110.0,
    }
    mock_ticker.fast_info = MagicMock()
    mock_ticker.fast_info.last_price = 100.0

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = _fetch_analyst_consensus_sync("NVDA", previous_target=None)

    assert result is not None
    assert result["net_changes_30d"] < 0  # net downgrades (sell+strongSell > buy+strongBuy in recent periods)
    assert result["mean_target"] == 90.0


def test_build_analyst_revision_candidate_warning_on_downgrades():
    from app.services.market_data import _build_analyst_revision_candidate

    consensus = {
        "net_changes_30d": -3,
        "mean_target": 90.0,
        "current_price": 95.0,
        "previous_target": 95.0,
    }
    candidate = _build_analyst_revision_candidate(consensus)
    assert candidate is not None
    priority, c = candidate
    assert c["event_type"] == "analyst_revision"
    assert "downgrade" in c["description"].lower() or "net" in c["description"].lower()


def test_analyst_revision_not_fired_below_threshold():
    from app.services.market_data import _build_analyst_revision_candidate

    # Only 1 change, target moved <10% — below both firing thresholds
    consensus = {
        "net_changes_30d": -1,
        "mean_target": 100.0,
        "current_price": 95.0,
        "previous_target": 97.0,
    }
    candidate = _build_analyst_revision_candidate(consensus)
    assert candidate is None


def test_fetch_analyst_consensus_handles_missing_columns():
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from app.services.market_data import _fetch_analyst_consensus_sync

    mock_ticker = MagicMock()
    # DataFrame missing strongBuy/strongSell columns
    mock_ticker.recommendations = pd.DataFrame({
        "period": ["0m", "-1m"],
        "buy": [3, 2],
        "hold": [5, 4],
        "sell": [2, 1],
    })
    mock_ticker.analyst_price_targets = {"mean": 95.0}
    mock_ticker.fast_info = MagicMock()
    mock_ticker.fast_info.last_price = 90.0

    with patch("yfinance.Ticker", return_value=mock_ticker):
        result = _fetch_analyst_consensus_sync("NVDA", previous_target=None)

    assert result is not None  # Should not raise or return None
    assert result["net_changes_30d"] == (3 + 2) - (2 + 1)  # upgrades - downgrades (no strongBuy/strongSell)
