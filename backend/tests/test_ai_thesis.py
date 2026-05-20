from unittest.mock import AsyncMock, patch

from app.services.ai_thesis import (
    ThesisAssistOutput,
    _fallback_assist,
    _fallback_synthesize,
    _parse_draft_output,
    assist_thesis,
)


async def test_assist_thesis_returns_structured_output():
    mock_ai_response = ThesisAssistOutput(
        why_own_it="Apple's ecosystem and services base create durable customer lock-in.",
        must_remain_true="Customer retention stays high and services growth remains resilient.",
        what_would_change_my_mind="Meaningful ecosystem weakening or sustained services deterioration.",
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
    assert result.why_own_it.startswith("Apple")
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
    assert result.why_own_it == "My friend recommended it."
    assert result.interpretation["monitorability"] == "low"
    assert result.interpretation["ambiguity_note"] != ""
    assert result.interpretation["watch_hints"] == []


async def test_assist_thesis_returns_none_when_strict_and_ai_fails():
    with patch("app.services.ai_thesis.settings.anthropic_api_key", "test-key"):
        with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, side_effect=Exception("API error")):
            with patch("app.services.ai_thesis.settings.openai_api_key", ""):
                result = await assist_thesis(
                    ticker="AAPL",
                    name="Apple Inc",
                    quantity=10,
                    average_cost=150.50,
                    draft_text="I own it for ecosystem strength.",
                    allow_fallback=False,
                )

    assert result is None


async def test_assist_thesis_falls_back_to_openai_when_anthropic_fails():
    openai_output = ThesisAssistOutput(
        why_own_it="Apple's ecosystem strength and switching costs remain durable.",
        must_remain_true="Retention stays high and services growth remains resilient.",
        what_would_change_my_mind="Ecosystem weakening or sustained retention deterioration.",
        ai_summary="Apple is owned for ecosystem durability.",
        interpretation={
            "labels": ["quality", "ecosystem"],
            "monitorability": "high",
            "watch_hints": [],
            "ambiguity_note": "",
        },
    )
    with patch("app.services.ai_thesis.settings.anthropic_api_key", "test-key"):
        with patch("app.services.ai_thesis.settings.openai_api_key", "openai-key"):
            with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, side_effect=Exception("Anthropic failed")):
                with patch("app.services.ai_thesis._call_openai_assist", new_callable=AsyncMock, return_value=openai_output):
                    result = await assist_thesis(
                        ticker="AAPL",
                        name="Apple Inc",
                        quantity=10,
                        average_cost=150.50,
                        draft_text="I own it for ecosystem strength.",
                        allow_fallback=False,
                    )

    assert result is not None
    assert result.ai_summary == "Apple is owned for ecosystem durability."
    assert result.why_own_it.startswith("Apple")


def test_fallback_assist_does_not_generate_proxy_signals():
    """Proxy decomposition is AI-only — the fallback returns empty proxy_signals."""
    result = _fallback_assist("ASML", why_own_it=None, must_remain_true=None, what_would_change_my_mind=None, draft_text="AI will drive semiconductor demand")
    assert result.interpretation["proxy_signals"] == []
    assert result.interpretation["monitorability"] == "medium"


def test_fallback_assist_vague_thesis():
    result = _fallback_assist("AAPL", why_own_it=None, must_remain_true=None, what_would_change_my_mind=None, draft_text="A friend recommended it")
    assert result.interpretation["proxy_signals"] == []
    assert result.interpretation["monitorability"] == "low"


def test_fallback_assist_empty_draft():
    result = _fallback_assist("AAPL", why_own_it=None, must_remain_true=None, what_would_change_my_mind=None, draft_text="")
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


def test_parse_draft_output_sanitizes_stale_administration_references():
    result = _parse_draft_output(
        {
            "why_own_it": "Tesla benefits if the Biden administration's charging rules favor NACS.",
            "must_remain_true": "The Biden administration's standards continue to support adoption.",
            "what_would_change_my_mind": "If the Biden administration's policy is reversed.",
        },
        "TSLA",
    )
    assert "Biden" not in result["why_own_it"]
    assert "Biden" not in result["must_remain_true"]
    assert "Biden" not in result["what_would_change_my_mind"]
    assert "U.S. federal policy" in result["why_own_it"]


def test_fallback_synthesize_for_hearsay_investor_sharpens_break_condition():
    result = _fallback_synthesize(
        ticker="NVDA",
        answer1="People kept talking about AI winners and this seemed like the one to own.",
        answer2="",
        investor_profile="hearsay_driven",
    )
    assert "story stops showing up in the operating results" in result.what_would_change_my_mind
    assert result.why_own_it.startswith("People kept talking") or "rough idea" in result.why_own_it
