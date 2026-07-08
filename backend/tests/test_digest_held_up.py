"""Tests for the 'Held up this week' section in the weekly digest.

Focuses on the pure split + render helpers so we don't need the DB path.
"""
from app.jobs.digest_builder import (
    _pick_held_up_events,
    _render_held_up_section,
)


def _event(ticker: str, verdict: str, *, severity: str = "info", title: str = "T") -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "severity": severity,
        "title": title,
        "summary": "s",
        "verdict": verdict,
        "evidence_summary": "e",
        "signal_status_text": "1 signal intact",
    }


def test_pick_only_returns_supports_verdicts():
    events = [
        _event("NVDA", "threatens"),
        _event("AAPL", "supports"),
        _event("MSFT", "neutral"),
        _event("TSLA", "review"),
    ]
    picked = _pick_held_up_events(events)
    assert [e["ticker"] for e in picked] == ["AAPL"]


def test_pick_caps_at_one_per_position():
    events = [
        _event("NVDA", "supports", title="1"),
        _event("NVDA", "supports", title="2"),
        _event("NVDA", "supports", title="3"),
    ]
    picked = _pick_held_up_events(events, max_per_position=1)
    assert len(picked) == 1


def test_pick_caps_at_max_total_across_positions():
    events = [_event(t, "supports") for t in ("NVDA", "AAPL", "MSFT", "GOOG", "META")]
    picked = _pick_held_up_events(events, max_total=3)
    assert len(picked) == 3


def test_pick_prefers_higher_severity_supports():
    # A thesis_breaking supports event ("management explicitly widened the
    # moat") is a much stronger validation than a routine info-tier support.
    events = [
        _event("NVDA", "supports", severity="info", title="Routine"),
        _event("AAPL", "supports", severity="thesis_breaking", title="Strong"),
    ]
    picked = _pick_held_up_events(events, max_total=1)
    assert picked[0]["title"] == "Strong"


def test_render_empty_when_no_items():
    assert _render_held_up_section([]) == ""


def test_render_uses_positive_framing_not_alert_language():
    # Regression guard: a supports event styled with alert words defeats the
    # emotional-balance point of this whole section.
    items = [_event("NVDA", "supports", title="Q1 beat driven by services growth")]
    html = _render_held_up_section(items)
    assert "Held up this week" in html
    assert "NVDA" in html
    assert "Q1 beat driven by services growth" in html
    for hostile in ("Threat", "needs review", "Review this reason", "at risk"):
        assert hostile not in html
