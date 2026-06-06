from unittest.mock import AsyncMock, patch

from app.services.ai_thesis import (
    ThesisAssistOutput,
    _apply_synthesis_guardrails,
    _fallback_assist,
    _fallback_initial_draft,
    _fallback_synthesize,
    _parse_assist_output,
    _parse_synthesis_output,
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
    assert any(hint["kind"] == "price_move_pct" for hint in result.interpretation["watch_hints"])
    assert any(hint["kind"] == "metric_threshold" for hint in result.interpretation["watch_hints"])


async def test_assist_thesis_falls_back_when_ai_fails():
    # Disable the OpenAI fallback so we exercise the deterministic no-AI fallback,
    # not whatever live OPENAI_API_KEY happens to be in the environment.
    with patch("app.services.ai_thesis.settings.anthropic_api_key", "test-key"):
        with patch("app.services.ai_thesis.settings.openai_api_key", ""):
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


def test_normalize_interpretation_repairs_below_threshold_metric_operator():
    from app.services.ai_thesis import _normalize_interpretation

    interpretation = {
        "labels": ["growth"],
        "monitorability": "high",
        "watch_hints": [
            {
                "kind": "metric_threshold",
                "metric": "revenue_growth_yoy",
                "operator": "<",
                "threshold": 0.10,
                "rationale": "Revenue growth falling below 10% would weaken the thesis.",
            }
        ],
        "proxy_signals": [],
        "ambiguity_note": "",
    }

    result = _normalize_interpretation(interpretation)
    metric_hint = next(hint for hint in result["watch_hints"] if hint.get("kind") == "metric_threshold")
    assert metric_hint["operator"] == ">="


def test_normalize_interpretation_repairs_above_threshold_metric_operator():
    from app.services.ai_thesis import _normalize_interpretation

    interpretation = {
        "labels": ["valuation"],
        "monitorability": "high",
        "watch_hints": [
            {
                "kind": "metric_threshold",
                "metric": "pe_ratio",
                "operator": ">",
                "threshold": 35.0,
                "rationale": "If the P/E ratio rises above 35, valuation gets too expensive.",
            }
        ],
        "proxy_signals": [],
        "ambiguity_note": "",
    }

    result = _normalize_interpretation(interpretation)
    metric_hint = next(hint for hint in result["watch_hints"] if hint.get("kind") == "metric_threshold")
    assert metric_hint["operator"] == "<="


def test_normalize_interpretation_keeps_news_watch_hints():
    from app.services.ai_thesis import _normalize_interpretation

    interpretation = {
        "labels": ["regulation"],
        "monitorability": "high",
        "watch_hints": [
            {
                "kind": "news_watch",
                "watch_for": "the FDA restricts compounded GLP-1 and the company has no replacement path by next earnings",
                "direction": "threatens",
                "rationale": "This would impair the main growth driver.",
            }
        ],
        "proxy_signals": [],
        "ambiguity_note": "",
    }

    result = _normalize_interpretation(interpretation)
    news_hint = next(hint for hint in result["watch_hints"] if hint.get("kind") == "news_watch")
    assert news_hint["direction"] == "threatens"
    assert "FDA restricts" in news_hint["watch_for"]


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


def test_fallback_assist_infers_qualitative_watch_rules_from_regulatory_and_deal_risk():
    result = _fallback_assist(
        "HIMS",
        why_own_it=(
            "I need Hims to keep generating meaningful GLP-1 prescription volume through their platform "
            "and I am watching whether the Eucalyptus deal actually delivers new revenue lines rather than becoming an overhead drag."
        ),
        must_remain_true=None,
        what_would_change_my_mind=(
            "I'd sell if the FDA bans compounded GLP-1 and Hims cannot pivot to a replacement quickly."
        ),
        draft_text=None,
    )

    news_hints = [hint for hint in result.interpretation["watch_hints"] if hint.get("kind") == "news_watch"]
    assert any("compounded GLP-1" in hint.get("watch_for", "") for hint in news_hints)
    assert any("replacement or mitigation path by next earnings" in hint.get("watch_for", "") for hint in news_hints)
    assert any("Eucalyptus" in hint.get("watch_for", "") for hint in news_hints)


def test_parse_assist_output_merges_qualitative_story_hints_ahead_of_generic_price_rule():
    raw = ThesisAssistOutput(
        why_own_it=(
            "I need Hims to keep generating meaningful GLP-1 prescription volume through their platform. "
            "I am also watching whether the Eucalyptus deal actually delivers new revenue lines rather than becoming an overhead drag."
        ),
        must_remain_true=(
            "Compounded semaglutide must stay available long enough for Hims to pivot quickly if the FDA restricts it."
        ),
        what_would_change_my_mind=(
            "I would sell if the FDA bans compounded GLP-1 medications and Hims has no credible replacement pipeline within one earnings cycle."
        ),
        ai_summary="HIMS thesis.",
        interpretation={
            "labels": ["regulatory_risk", "M&A_execution"],
            "monitorability": "high",
            "watch_hints": [
                {
                    "kind": "metric_threshold",
                    "metric": "gross_margin_qoq",
                    "operator": "<",
                    "threshold": -0.05,
                    "rationale": "Gross margin compressing would signal the GLP-1 profit risk is real.",
                },
                {
                    "kind": "price_move_pct",
                    "threshold": 15.0,
                    "rationale": "A sharp price decline warrants review.",
                },
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        },
    )

    result = _parse_assist_output(raw)

    assert [hint["kind"] for hint in result.interpretation["watch_hints"]] == [
        "news_watch",
        "news_watch",
        "metric_threshold",
    ]
    assert any("replacement or mitigation path by next earnings" in hint.get("watch_for", "") for hint in result.interpretation["watch_hints"])
    assert any("Eucalyptus" in hint.get("watch_for", "") for hint in result.interpretation["watch_hints"])
    assert not any(hint.get("kind") == "price_move_pct" for hint in result.interpretation["watch_hints"])


def test_parse_draft_output_rewrites_generic_placeholder_language():
    result = _parse_draft_output(
        {
            "why_own_it": "Holding NVDA as a core position in the portfolio.",
            "must_remain_true": "The company maintains its market position.",
            "what_would_change_my_mind": "A fundamental change in the business model.",
        },
        "NVDA",
    )
    assert "core position in the portfolio" not in result["why_own_it"]
    assert "maintains its market position" not in result["must_remain_true"]
    assert "fundamental change in the business model" not in result["what_would_change_my_mind"]
    assert "operating results" in result["what_would_change_my_mind"]


def test_fallback_initial_draft_uses_market_data_when_available():
    class DummyMarketData:
        sector = "Technology"
        industry = "Semiconductors"
        revenue_growth_yoy = 0.24
        earnings_growth_yoy = 0.12

    result = _fallback_initial_draft("NVDA", DummyMarketData())
    assert "semiconductors" in result["why_own_it"].lower()
    assert "revenue growth" in result["must_remain_true"].lower()
    assert "position should be reconsidered" in result["what_would_change_my_mind"].lower()


def test_fallback_synthesize_for_hearsay_investor_sharpens_break_condition():
    result = _fallback_synthesize(
        ticker="NVDA",
        answer1="People kept talking about AI winners and this seemed like the one to own.",
        answer2="",
        investor_profile="hearsay_driven",
    )
    assert "management commentary stops backing the original growth story" in result.what_would_change_my_mind
    assert result.why_own_it.startswith("People kept talking") or "rough idea" in result.why_own_it
    assert "demand story in NVDA" in result.must_remain_true
    assert any(
        hint.get("kind") == "metric_threshold" and hint.get("metric") == "revenue_growth_yoy"
        for hint in result.interpretation["watch_hints"]
    )


def test_parse_synthesis_output_for_hearsay_rewrites_generic_conditions():
    result = _parse_synthesis_output(
        {
            "why_own_it": "Everyone was talking about the AI trade and NVDA seemed like the obvious winner.",
            "must_remain_true": "The core investment thesis for NVDA remains intact.",
            "what_would_change_my_mind": "A fundamental change in the business model.",
            "ai_summary": "Story-driven NVDA idea.",
            "interpretation": {
                "labels": ["growth"],
                "monitorability": "low",
                "watch_hints": [],
                "proxy_signals": [],
                "ambiguity_note": "",
            },
        },
        "NVDA",
        answer1="Everyone was talking about the AI trade and NVDA seemed like the obvious winner.",
        answer2="If growth fades for a few quarters.",
        investor_profile="hearsay_driven",
    )
    assert "demand story in NVDA" in result.must_remain_true
    assert "position should be reconsidered" in result.what_would_change_my_mind
    assert result.interpretation["monitorability"] == "medium"
    assert result.interpretation["ambiguity_note"] != ""
    assert any(
        hint.get("kind") == "metric_threshold" and hint.get("metric") == "revenue_growth_yoy"
        for hint in result.interpretation["watch_hints"]
    )


def test_apply_synthesis_guardrails_preserves_non_hearsay_outputs():
    base = _fallback_synthesize(
        ticker="MSFT",
        answer1="Azure growth and enterprise distribution should keep compounding cash flow.",
        answer2="If cloud growth stalls and margins compress.",
        investor_profile="thesis_driven",
    )
    result = _apply_synthesis_guardrails(
        base,
        ticker="MSFT",
        answer1="Azure growth and enterprise distribution should keep compounding cash flow.",
        answer2="If cloud growth stalls and margins compress.",
        investor_profile="thesis_driven",
    )
    assert result.must_remain_true == base.must_remain_true
    assert result.what_would_change_my_mind == base.what_would_change_my_mind


def test_fallback_synthesize_for_thesis_driven_avoids_generic_conditions():
    result = _fallback_synthesize(
        ticker="ASML",
        answer1="The EUV backlog and chipmaker capex cycle should keep demand strong.",
        answer2="",
        investor_profile="thesis_driven",
    )
    assert "core investment thesis" not in result.must_remain_true.lower()
    assert "demand" in result.must_remain_true.lower()
    assert "management commentary" in result.what_would_change_my_mind.lower() or "demand softens" in result.what_would_change_my_mind.lower()


def test_parse_synthesis_output_for_thesis_driven_rewrites_generic_conditions():
    result = _parse_synthesis_output(
        {
            "why_own_it": "I own ASML because EUV demand and the chip capex cycle should stay strong.",
            "must_remain_true": "The core investment thesis for ASML remains intact.",
            "what_would_change_my_mind": "A fundamental change in the business model.",
            "ai_summary": "ASML thesis.",
            "interpretation": {
                "labels": ["growth"],
                "monitorability": "low",
                "watch_hints": [],
                "proxy_signals": [],
                "ambiguity_note": "",
            },
        },
        "ASML",
        answer1="I own ASML because EUV demand and the chip capex cycle should stay strong.",
        answer2="If demand weakens and management stops backing the cycle.",
        investor_profile="thesis_driven",
    )
    assert "core investment thesis" not in result.must_remain_true.lower()
    assert "demand" in result.must_remain_true.lower()
    assert "position should be reconsidered" in result.what_would_change_my_mind.lower()
    assert result.interpretation["monitorability"] == "medium"
    assert any(
        hint.get("kind") == "metric_threshold" and hint.get("metric") == "revenue_growth_yoy"
        for hint in result.interpretation["watch_hints"]
    )
