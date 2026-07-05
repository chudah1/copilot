"""Tests for the thesis-aware relevance filter.

The filter calls gpt-4o-mini per news candidate. Tests use mocked OpenAI
responses to verify the keep/drop logic and the tagging of matched
signals into evidence.relevant_signals (so the existing label-binding
path can pick them up downstream).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thesis_relevance_filter import (
    _RELEVANCE_FILTER_EVENT_TYPES,
    filter_candidates_by_thesis_relevance,
    filter_candidates_by_thesis_relevance_with_drops,
)


def _make_news_candidate(headline: str, summary: str = "", event_type: str = "news_or_earnings_candidate") -> dict:
    return {
        "event_type": event_type,
        "description": headline,
        "evidence": {"headline": headline, "summary": summary},
    }


def _mock_openai_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return resp


@pytest.mark.asyncio
async def test_filter_drops_fund_flow_noise_keeps_thesis_news(monkeypatch):
    """Walkthrough surfaced 13F-style filings ('Fund X reduced AAPL holdings by 0.8%')
    surviving the keyword filter and reaching classification as info. The
    relevance filter should drop them so the user's notification stream stays
    focused on signal-relevant news."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )

    fund_flow = _make_news_candidate(
        "Adams Diversified Equity Fund Inc. reduced its holdings of AAPL by 0.8%",
        "Adams Diversified sold 6,500 shares of Apple in the fourth quarter.",
    )
    thesis_news = _make_news_candidate(
        "Apple Faces a No-Win Pricing Dilemma. Should Investors Be Worried?",
        "Apple maintains impressive gross margins of around 39% for its products, "
        "though the Q2 product gross margin decreased slightly due to seasonal "
        "leverage loss and higher memory costs.",
    )

    fund_flow_response = _mock_openai_response({"relevant": False, "matched_signals": []})
    thesis_news_response = _mock_openai_response(
        {"relevant": True, "matched_signals": ["AAPL Hardware gross margin trend"]}
    )

    async def fake_create(**kwargs):
        prompt = kwargs["messages"][0]["content"]
        return thesis_news_response if "Pricing Dilemma" in prompt else fund_flow_response

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await filter_candidates_by_thesis_relevance(
            [fund_flow, thesis_news],
            signal_descriptors=[{"label": "AAPL Hardware gross margin trend", "claim_text": "Apple Hardware gross margin stays above 35%"}],
            ticker="AAPL",
            why_own_it="Apple Services is a high-margin recurring revenue stream.",
        )

    assert len(result) == 1
    assert result[0] is thesis_news
    # The LLM's matched-signal hint should land on evidence.relevant_signals
    # so the existing label-binding path picks it up downstream.
    assert result[0]["evidence"]["relevant_signals"] == ["AAPL Hardware gross margin trend"]


@pytest.mark.asyncio
async def test_filter_noop_when_no_signal_descriptors():
    """During onboarding the thesis may not yet have any signals extracted.
    Dropping candidates in that state would erase the first-pulse experience
    — the filter must be a no-op when there's nothing to judge against."""
    fund_flow = _make_news_candidate("Some institutional holding update")
    result = await filter_candidates_by_thesis_relevance(
        [fund_flow],
        signal_descriptors=[],
        ticker="AAPL",
        why_own_it="brand and ecosystem.",
    )
    assert result == [fund_flow]


@pytest.mark.asyncio
async def test_filter_leaves_non_news_event_types_alone(monkeypatch):
    """price_move, earnings_surprise, watch_hint_breach etc. are already
    grounded in stated thresholds — the relevance filter should not touch
    them, even if it's running."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )

    price_move = {"event_type": "price_move", "description": "AAPL down 8%", "evidence": {}}
    earnings = {"event_type": "earnings_surprise", "description": "Beat by 5%", "evidence": {}}

    fake_create = AsyncMock(side_effect=AssertionError("LLM should not be called for non-news events"))
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await filter_candidates_by_thesis_relevance(
            [price_move, earnings],
            signal_descriptors=[{"label": "x", "claim_text": "y"}],
            ticker="AAPL",
            why_own_it="z",
        )

    assert result == [price_move, earnings]


@pytest.mark.asyncio
async def test_filter_keeps_candidate_when_llm_errors(monkeypatch):
    """A transient OpenAI error must not silently drop news. Default to keep
    — the downstream classifier will still get a chance to call skip."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )
    news = _make_news_candidate("Apple announces something")

    fake_create = AsyncMock(side_effect=RuntimeError("transient 503"))
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await filter_candidates_by_thesis_relevance(
            [news],
            signal_descriptors=[{"label": "AAPL services", "claim_text": "services growth"}],
            ticker="AAPL",
            why_own_it="brand.",
        )

    assert result == [news]


@pytest.mark.asyncio
async def test_filter_keeps_candidate_when_llm_returns_invalid_json(monkeypatch):
    """If the model returns malformed JSON, default to keep (same as the
    transient error path) so we never silently drop news on a parse failure."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )
    news = _make_news_candidate("Apple announces something")

    bad_response = MagicMock()
    bad_response.choices = [MagicMock(message=MagicMock(content="not json at all"))]

    fake_create = AsyncMock(return_value=bad_response)
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        result = await filter_candidates_by_thesis_relevance(
            [news],
            signal_descriptors=[{"label": "AAPL services", "claim_text": "services growth"}],
            ticker="AAPL",
            why_own_it="brand.",
        )

    assert result == [news]


@pytest.mark.asyncio
async def test_with_drops_variant_captures_reason_and_metadata(monkeypatch):
    """The digest's 'reviewed this week' section needs both the LLM's
    plain-english reason and enough evidence context (headline, source,
    matched signal labels) to render a curated snippet."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )

    fund_flow = {
        "event_type": "gemini_news",
        "description": "Vanguard trimmed AAPL by 0.2% in Q1",
        "evidence": {
            "headline": "Vanguard trimmed AAPL by 0.2% in Q1",
            "summary": "Institutional 13F filing.",
            "url": "https://example.com/vanguard",
            "published_at": "2026-07-01T10:00:00Z",
        },
    }

    response = _mock_openai_response({
        "relevant": False,
        "matched_signals": [],
        "reason": "This is a 13F institutional-holding update, which doesn't touch your services-growth pillar.",
    })

    fake_create = AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        kept, dropped = await filter_candidates_by_thesis_relevance_with_drops(
            [fund_flow],
            signal_descriptors=[{"label": "AAPL services growth", "claim_text": "services grows above 15% YoY"}],
            ticker="AAPL",
            why_own_it="Services is a durable high-margin engine.",
        )

    assert kept == []
    assert len(dropped) == 1
    drop = dropped[0]
    assert drop.headline == "Vanguard trimmed AAPL by 0.2% in Q1"
    assert drop.source == "gemini_news"
    assert drop.ticker == "AAPL"
    assert drop.url == "https://example.com/vanguard"
    assert drop.published_at == "2026-07-01T10:00:00Z"
    assert "13F" in drop.reason
    assert "services-growth pillar" in drop.reason


@pytest.mark.asyncio
async def test_with_drops_variant_omits_drops_with_empty_reason(monkeypatch):
    """The LLM might mark relevant=false without producing a reason (parse
    error, model quirk). We can't honestly show these to the user, so skip
    them from the reviewed-this-week payload — the drop still happens for
    the kept-candidates return value."""
    monkeypatch.setattr(
        "app.services.thesis_relevance_filter.settings.openai_api_key", "test-key", raising=False
    )

    news = _make_news_candidate("Some ambiguous news")

    response = _mock_openai_response({"relevant": False, "matched_signals": []})  # no reason

    fake_create = AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        kept, dropped = await filter_candidates_by_thesis_relevance_with_drops(
            [news],
            signal_descriptors=[{"label": "AAPL services", "claim_text": "growth"}],
            ticker="AAPL",
            why_own_it="brand.",
        )

    assert kept == []
    assert dropped == []


def test_relevance_filter_targets_all_news_style_event_types():
    """Catch new event types added to the news pipeline that aren't getting
    filtered — the relevance filter is supposed to cover gemini_news,
    yfinance/AV news, product_ramp_update, and the various proxy news types."""
    expected_news_event_types = {
        "news_or_earnings_candidate",
        "product_ramp_update",
        "news_keyword_match",
        "gemini_news",
    }
    missing = expected_news_event_types - _RELEVANCE_FILTER_EVENT_TYPES
    assert not missing, f"Filter should target {missing} but doesn't"
