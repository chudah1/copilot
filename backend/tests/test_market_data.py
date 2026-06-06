from datetime import datetime, timedelta, timezone

from app.services.market_data import _TTLCache, QUALITATIVE_KEYWORDS
from app.services.market_data import (
    _build_company_data_from_alpha_vantage,
    _parse_alpha_vantage_earnings,
    _parse_alpha_vantage_earnings_calendar,
    _parse_alpha_vantage_insider_transactions,
    _parse_alpha_vantage_news,
    _parse_alpha_vantage_overview,
    _parse_alpha_vantage_quote,
    _parse_alpha_vantage_transcript,
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
