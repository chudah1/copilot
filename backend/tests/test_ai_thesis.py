from unittest.mock import AsyncMock, patch

from app.services.ai_thesis import ThesisAssistOutput, _fallback_assist, assist_thesis


async def test_assist_thesis_returns_structured_output():
    mock_ai_response = ThesisAssistOutput(
        ai_summary="Apple is owned for durable ecosystem strength and recurring cash generation.",
        interpretation={
            "labels": ["quality", "ecosystem"],
            "monitorability": "high",
            "watch_hints": [
                {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Demand should stay healthy."}
            ],
            "ambiguity_note": "",
        },
    )
    with patch("app.services.ai_thesis.settings.anthropic_api_key", "test-key"):
        with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, return_value=mock_ai_response):
            result = await assist_thesis(
                ticker="AAPL",
                name="Apple Inc",
                quantity=10,
                average_cost=150.50,
                draft_text="I own it for its ecosystem and margins.",
            )

    assert result is not None
    assert result.ai_summary != ""
    assert result.interpretation["monitorability"] == "high"
    assert result.interpretation["watch_hints"][0]["kind"] == "price_move_pct"
    assert any(hint["kind"] == "metric_threshold" for hint in result.interpretation["watch_hints"])


async def test_assist_thesis_falls_back_when_ai_fails():
    with patch("app.services.ai_thesis.settings.anthropic_api_key", "test-key"):
        with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, side_effect=Exception("API error")):
            result = await assist_thesis(
                ticker="AAPL",
                name="Apple Inc",
                quantity=10,
                average_cost=150.50,
                draft_text="My friend recommended it.",
            )

    assert result is not None
    assert "AAPL" in result.ai_summary
    assert result.interpretation["monitorability"] == "low"
    assert result.interpretation["ambiguity_note"] != ""
    assert result.interpretation["watch_hints"] == []


def test_fallback_assist_does_not_generate_proxy_signals():
    """Proxy decomposition is AI-only — the fallback returns empty proxy_signals."""
    result = _fallback_assist("ASML", "AI will drive semiconductor demand")
    assert result.interpretation["proxy_signals"] == []
    assert result.interpretation["monitorability"] == "medium"


def test_fallback_assist_vague_thesis():
    result = _fallback_assist("AAPL", "A friend recommended it")
    assert result.interpretation["proxy_signals"] == []
    assert result.interpretation["monitorability"] == "low"


def test_fallback_assist_empty_draft():
    result = _fallback_assist("AAPL", "")
    assert result.interpretation["proxy_signals"] == []


def test_normalize_interpretation_deduplicates_proxy_tickers():
    from app.services.ai_thesis import _normalize_interpretation
    interpretation = {
        "labels": ["growth"],
        "monitorability": "high",
        "watch_hints": [],
        "proxy_signals": [
            {"ticker": "NVDA", "rationale": "First reason", "signal_hint": "data center demand"},
            {"ticker": "nvda", "rationale": "Duplicate"},
            {"ticker": "TSM", "rationale": "Foundry"},
        ],
    }
    result = _normalize_interpretation(interpretation)
    tickers = [p["ticker"] for p in result["proxy_signals"]]
    assert tickers == ["NVDA", "TSM"]
    assert result["proxy_signals"][0]["signal_hint"] == "data center demand"


def test_normalize_interpretation_filters_invalid_proxy_tickers():
    from app.services.ai_thesis import _normalize_interpretation
    interpretation = {
        "labels": ["growth"],
        "monitorability": "high",
        "watch_hints": [],
        "proxy_signals": [
            {"ticker": "bad symbol!", "rationale": "Invalid"},
            {"ticker": "MSFT", "rationale": "Valid proxy", "signal_hint": "capex guidance"},
        ],
    }
    result = _normalize_interpretation(interpretation)
    assert result["proxy_signals"] == [
        {"ticker": "MSFT", "rationale": "Valid proxy", "signal_hint": "capex guidance"}
    ]
