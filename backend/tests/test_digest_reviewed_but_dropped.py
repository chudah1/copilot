"""Tests for the adjacency-evidence surface in the digest.

Focuses on the pure curation + render helpers so we can assert the desired
behaviour without spinning up the whole digest-build DB path. The DB loader
is exercised indirectly through the existing integration tests.
"""
from datetime import datetime, timezone

from app.jobs.digest_builder import (
    _curate_reviewed_but_dropped,
    _render_reviewed_but_dropped_section,
)


def _drop(**overrides) -> dict:
    base = {
        "ticker": "NVDA",
        "holding_id": "h1",
        "headline": "Some article about NVDA",
        "reason": "A substantive plain sentence about why the article does not touch the thesis.",
        "source": "gemini_news",
        "url": "https://example.com/x",
        "published_at": "2026-07-03T10:00:00+00:00",
        "matched_signal_labels": ["CUDA moat"],
    }
    base.update(overrides)
    return base


def test_curate_caps_at_two_items_one_per_holding():
    # Three drops on the same holding should collapse to one — user wants
    # breadth across the portfolio, not repeated NVDA drops.
    drops = [
        _drop(headline="A"),
        _drop(headline="B"),
        _drop(headline="C"),
        _drop(ticker="AAPL", holding_id="h2", headline="D"),
        _drop(ticker="MSFT", holding_id="h3", headline="E"),
    ]
    result = _curate_reviewed_but_dropped(drops)
    tickers = [item["ticker"] for item in result]
    assert len(result) == 2
    assert len(set(tickers)) == 2


def test_curate_skips_tickers_already_covered_by_live_alerts():
    # If NVDA already has an event card in the digest, the reviewed block
    # shouldn't fight the alert with a second NVDA blurb. Show a different
    # ticker or nothing.
    drops = [
        _drop(ticker="NVDA", holding_id="h1"),
        _drop(ticker="AAPL", holding_id="h2", headline="Different"),
    ]
    result = _curate_reviewed_but_dropped(drops, holdings_covered={"NVDA"})
    assert [item["ticker"] for item in result] == ["AAPL"]


def test_curate_prefers_trusted_sources_over_yfinance_noise():
    # Same holding, same close-call rating — the Gemini item wins over the
    # yfinance one on tiebreak. Users associate yfinance news with fund-flow
    # noise, so it's a weaker "we actually looked" signal.
    drops = [
        _drop(source="news_or_earnings_candidate", headline="Yfinance take"),
        _drop(source="gemini_news", headline="Gemini take"),
    ]
    result = _curate_reviewed_but_dropped(drops)
    assert result[0]["headline"] == "Gemini take"


def test_curate_drops_items_with_terse_reasons():
    # A 5-character reason ('N/A.') is useless to show — no thesis specificity.
    # These would look like the app just deleted stuff without thinking.
    drops = [
        _drop(reason="N/A."),
        _drop(ticker="AAPL", holding_id="h2", reason="Way too short."),
    ]
    result = _curate_reviewed_but_dropped(drops)
    assert result == []


def test_curate_returns_empty_for_no_drops():
    assert _curate_reviewed_but_dropped([]) == []


def test_render_section_is_empty_when_no_items():
    html = _render_reviewed_but_dropped_section([], now=datetime.now(timezone.utc))
    assert html == ""


def test_render_section_includes_ticker_headline_and_reason():
    now = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)
    items = [
        _drop(
            ticker="NVDA",
            headline="Analyst downgrade on China exposure",
            reason="The downgrade is about near-term China revenue exposure, which does not touch your CUDA moat pillar.",
            published_at="2026-07-01T10:00:00+00:00",
        ),
    ]
    html = _render_reviewed_but_dropped_section(items, now=now)
    assert "Reviewed this week" in html
    assert "NVDA" in html
    assert "Analyst downgrade on China exposure" in html
    assert "CUDA moat pillar" in html
    # 4-day gap should read as "4d ago".
    assert "4d ago" in html


def test_render_section_html_escapes_hostile_input():
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    items = [
        _drop(
            headline="<script>alert('x')</script>",
            reason="Attempt to inject &lt;html&gt;.",
        )
    ]
    html = _render_reviewed_but_dropped_section(items, now=now)
    assert "<script>alert" not in html  # escaped, not literal
    assert "&lt;script&gt;" in html
