"""Golden-set tests for the pure / deterministic helpers in ai_thesis.py.

No network, no API calls. Tests cover:
  vague         — classic short/hearsay/boilerplate inputs
  keyword-trap  — short thesis with only thematic driver keywords (FAILS before Task 3)
  substring-trap — bare `in` false positives (FAILS before Task 2)
  unit-trap     — growth metric threshold given as percent int (FAILS before Task 4)
  specific/good — real thesis must pass untouched
  self-consistency — fallback strings must not contain banned patterns (FAILS before Task 1)
  dedupe        — semantic dedupe keeps better threshold (FAILS before Task 5)
"""

import re

import pytest

from app.services.ai_thesis import (
    GENERIC_CONDITION_PATTERNS,
    GENERIC_OUTPUT_PATTERNS,
    _dedupe_watch_hints,
    _detect_monitorable_drivers,
    _fallback_assist,
    _infer_hearsay_conditions,
    _infer_specific_conditions,
    _infer_story_watch_hints,
    _normalize_interpretation,
    _prioritize_watch_hints,
    assess_thesis_vagueness,
)


def _matches_banned(text: str, *pattern_groups) -> bool:
    lowered = text.lower()
    return any(
        re.search(p, lowered)
        for patterns in pattern_groups
        for p in patterns
    )


# =============================================================================
# VAGUE FAMILY
# =============================================================================


@pytest.mark.parametrize(
    "text,expected_reason",
    [
        ("friend recommended it", "vague_language"),
        ("long term hold", "vague_language"),
        ("They make iPhones.", "too_short"),
        ("heard it was going to run", "hearsay"),
        ("everyone was talking about it", "hearsay"),
    ],
)
def test_vague_texts_flagged(text, expected_reason):
    a = assess_thesis_vagueness(text)
    assert a.is_vague, f"Expected vague: {text!r}"
    assert expected_reason in a.reasons


# =============================================================================
# KEYWORD-TRAP FAMILY — FAILS before Task 3
# =============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "AI growth",
        "I own it for the AI growth",
    ],
)
def test_keyword_trap_short_thematic_only_is_vague(text):
    """Short thesis with only thematic driver keywords (no digit/%) must be vague."""
    a = assess_thesis_vagueness(text)
    assert a.is_vague, f"Expected vague for short keyword-only thesis: {text!r}"


# =============================================================================
# SPECIFIC / GOOD FAMILY
# =============================================================================


def test_specific_thesis_with_metric_and_threshold_not_vague():
    text = (
        "I own MSFT because Azure cloud is growing at 25%+ and I expect operating margins "
        "to stay above 40%. I would sell if cloud revenue growth falls below 15% for two quarters."
    )
    a = assess_thesis_vagueness(text)
    assert not a.is_vague
    assert "growth" in a.detected_drivers and "quality" in a.detected_drivers


def test_terse_thesis_with_concrete_numbers_not_vague():
    """Short but has concrete metric + threshold — must NOT be vague (regression guard for Task 3)."""
    a = assess_thesis_vagueness("Margins above 60%, FCF growing 20%.")
    assert not a.is_vague
    assert "quality" in a.detected_drivers


def test_hearsay_framing_vague_even_with_metrics_mentioned():
    """Strong hearsay framing overrides any driver — regression guard."""
    a = assess_thesis_vagueness("Everyone was talking about its revenue growth and margins.")
    assert a.is_vague


# =============================================================================
# SUBSTRING-TRAP FAMILY
# =============================================================================


def test_substring_trap_ideally_does_not_trigger_deal_hint():
    """'deal' substring in 'ideally' must NOT trigger acquisition watch hint.

    FAILS before Task 2 — bare `in` check matches 'deal' inside 'ideally'.
    """
    hints = _infer_story_watch_hints("ideally positioned in semiconductors")
    bad = [
        h for h in hints
        if h.get("kind") == "news_watch"
        and any(
            kw in h.get("watch_for", "").lower()
            for kw in ("deal", "acquisition", "integration")
        )
    ]
    assert bad == [], f"Unexpected acquisition hints triggered by 'ideally': {bad}"


def test_substring_trap_pe_in_europe_does_not_trigger_valuation_branch():
    """_infer_specific_conditions must not enter the valuation branch for 'europe'.

    FAILS before Task 2 — bare `in` check matches 'pe' inside 'europe'.
    """
    must, _change, _note = _infer_specific_conditions(
        "AAPL",
        why_text="I have broad exposure in Europe through this holding.",
        change_text="",
        investor_profile=None,
    )
    assert "justify the valuation" not in must


def test_detect_monitorable_drivers_word_boundary_for_ai():
    """'ai' must not match inside 'domain', 'email', 'maintain'."""
    assert "theme" not in _detect_monitorable_drivers("deep domain expertise and email marketing")
    assert "theme" in _detect_monitorable_drivers("AI demand is enormous")


# =============================================================================
# WORD-BOUNDARY REGRESSION GUARDS
# regression guard — _detect_monitorable_drivers already uses word boundaries
# =============================================================================


def test_substring_trap_europe_does_not_match_pe_driver():
    """'pe' inside 'europe' must NOT be detected as a valuation driver (regression guard)."""
    drivers = _detect_monitorable_drivers("exposure in Europe")
    assert "valuation" not in drivers


# =============================================================================
# UNIT-TRAP FAMILY — FAILS before Task 4
# =============================================================================


def test_normalize_interpretation_corrects_growth_metric_percent_threshold():
    """revenue_growth_yoy threshold=10.0 must be normalised to 0.10 (÷100)."""
    result = _normalize_interpretation(
        {
            "labels": ["growth"],
            "monitorability": "high",
            "watch_hints": [
                {
                    "kind": "metric_threshold",
                    "metric": "revenue_growth_yoy",
                    "operator": ">=",
                    "threshold": 10.0,
                    "rationale": "Revenue must grow at least 10%.",
                }
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        }
    )
    metric_hint = next(h for h in result["watch_hints"] if h.get("kind") == "metric_threshold")
    assert metric_hint["threshold"] == pytest.approx(0.10), (
        f"Expected 0.10 (fraction), got {metric_hint['threshold']} — unit not corrected"
    )


def test_normalize_interpretation_leaves_small_growth_threshold_unchanged():
    """revenue_growth_yoy threshold=0.15 (already a fraction) must stay at 0.15."""
    result = _normalize_interpretation(
        {
            "labels": ["growth"],
            "monitorability": "high",
            "watch_hints": [
                {
                    "kind": "metric_threshold",
                    "metric": "revenue_growth_yoy",
                    "operator": ">=",
                    "threshold": 0.15,
                    "rationale": "Revenue must grow at least 15%.",
                }
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        }
    )
    metric_hint = next(h for h in result["watch_hints"] if h.get("kind") == "metric_threshold")
    assert metric_hint["threshold"] == pytest.approx(0.15)


# =============================================================================
# SELF-CONSISTENCY FAMILY
# =============================================================================


def test_fallback_assist_empty_draft_no_banned_phrases():
    """_fallback_assist with no draft must not return boilerplate.

    FAILS before Task 1: must_remain_true = 'The underlying business case remains intact.'
    """
    result = _fallback_assist(
        "AAPL",
        why_own_it=None,
        must_remain_true=None,
        what_would_change_my_mind=None,
        draft_text=None,
    )
    for field_name, field_value in [
        ("must_remain_true", result.must_remain_true),
        ("what_would_change_my_mind", result.what_would_change_my_mind),
        ("why_own_it", result.why_own_it),
    ]:
        assert not _matches_banned(field_value, GENERIC_OUTPUT_PATTERNS, GENERIC_CONDITION_PATTERNS), (
            f"Banned phrase in {field_name}: {field_value!r}"
        )


def test_fallback_assist_vague_draft_no_banned_phrases():
    result = _fallback_assist(
        "TSLA",
        why_own_it=None,
        must_remain_true=None,
        what_would_change_my_mind=None,
        draft_text="friend recommended it",
    )
    for v in [result.must_remain_true, result.what_would_change_my_mind]:
        assert not _matches_banned(v, GENERIC_OUTPUT_PATTERNS, GENERIC_CONDITION_PATTERNS)


def test_infer_hearsay_conditions_no_banned_phrases():
    must, change, _ = _infer_hearsay_conditions(
        "NVDA", "Everyone was talking about the AI trade", ""
    )
    for v in [must, change]:
        assert not _matches_banned(v, GENERIC_OUTPUT_PATTERNS, GENERIC_CONDITION_PATTERNS)


def test_infer_specific_conditions_no_banned_phrases():
    must, change, _ = _infer_specific_conditions(
        "AAPL",
        why_text="I own it for the ecosystem lock-in and growing services revenue",
        change_text="",
        investor_profile=None,
    )
    for v in [must, change]:
        assert not _matches_banned(v, GENERIC_OUTPUT_PATTERNS, GENERIC_CONDITION_PATTERNS)


# =============================================================================
# DEDUPE / PRIORITIZE FAMILY — semantic dedupe FAILS before Task 5
# =============================================================================


def test_dedupe_removes_exact_duplicates():
    hints = [
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": "A"},
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": "A"},
        {"kind": "price_move_pct", "threshold": 5.0, "rationale": "B"},
    ]
    result = _dedupe_watch_hints(hints)
    assert len(result) == 2


def test_prioritize_orders_news_then_metric_then_price():
    hints = [
        {"kind": "price_move_pct", "threshold": 5.0, "rationale": ""},
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": ""},
        {"kind": "news_watch", "watch_for": "major regulatory change", "direction": "threatens", "rationale": ""},
    ]
    result = _prioritize_watch_hints(hints)
    assert result[0]["kind"] == "news_watch"
    assert result[1]["kind"] == "metric_threshold"
    assert result[2]["kind"] == "price_move_pct"


def test_semantic_dedupe_keeps_nonzero_threshold_over_zero():
    """Model's 0.10 threshold must survive against an inferred 0.0.

    FAILS before Task 5 — current dedupe uses exact tuple; both hints are kept.
    """
    hints = [
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": "Model hint"},
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "Inferred hint"},
        {"kind": "price_move_pct", "threshold": 5.0, "rationale": "Review trigger"},
    ]
    result = _dedupe_watch_hints(hints)
    revenue_hints = [
        h for h in result
        if h.get("kind") == "metric_threshold" and h.get("metric") == "revenue_growth_yoy"
    ]
    assert len(revenue_hints) == 1, f"Expected 1 revenue hint, got {len(revenue_hints)}: {revenue_hints}"
    assert revenue_hints[0]["threshold"] == pytest.approx(0.10)


def test_price_hint_not_evicted_after_metric_dedupe():
    """After 2 revenue hints are deduped to 1, the price_move hint must still be present."""
    hints = [
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": "A"},
        {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.0, "rationale": "B"},
        {"kind": "price_move_pct", "threshold": 5.0, "rationale": "C"},
    ]
    result = _prioritize_watch_hints(hints)
    assert any(h.get("kind") == "price_move_pct" for h in result)
    metric_revenue = [
        h for h in result
        if h.get("kind") == "metric_threshold" and h.get("metric") == "revenue_growth_yoy"
    ]
    assert len(metric_revenue) == 1


# =============================================================================
# _normalize_interpretation EDGE CASES
# =============================================================================


def test_normalize_interpretation_none_input_returns_defaults():
    result = _normalize_interpretation(None)
    assert result["monitorability"] == "low"
    assert result["proxy_signals"] == []
    assert result["labels"] == ["user_defined"]
    assert result["ambiguity_note"] == ""


def test_normalize_interpretation_preserves_news_watch_hint():
    result = _normalize_interpretation(
        {
            "labels": ["regulation"],
            "monitorability": "high",
            "watch_hints": [
                {
                    "kind": "news_watch",
                    "watch_for": "FDA formally restricts compounded GLP-1 and management fails to present a mitigation path",
                    "direction": "threatens",
                    "rationale": "Core revenue driver at risk.",
                }
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        }
    )
    news_hints = [h for h in result["watch_hints"] if h.get("kind") == "news_watch"]
    assert len(news_hints) >= 1
    assert "GLP-1" in news_hints[0]["watch_for"]


def test_normalize_interpretation_caps_at_three_watch_hints():
    result = _normalize_interpretation(
        {
            "labels": ["growth"],
            "monitorability": "high",
            "watch_hints": [
                {"kind": "news_watch", "watch_for": "w1", "direction": "threatens", "rationale": ""},
                {"kind": "news_watch", "watch_for": "w2", "direction": "supports", "rationale": ""},
                {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 0.10, "rationale": ""},
                {"kind": "price_move_pct", "threshold": 5.0, "rationale": ""},
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        }
    )
    assert len(result["watch_hints"]) <= 3


def test_infer_story_watch_hints_revenue_text_generates_metric_hint():
    hints = _infer_story_watch_hints("revenue growth and subscriber adoption are key")
    metric_kinds = [h.get("kind") for h in hints]
    assert "metric_threshold" in metric_kinds


def test_infer_story_watch_hints_fallback_includes_price_hint():
    hints = _infer_story_watch_hints("general holding for diversification")
    assert any(h.get("kind") == "price_move_pct" for h in hints)


# =============================================================================
# TASK 6: MaxTokensError is a distinct exception
# =============================================================================


def test_max_tokens_error_is_distinct():
    from app.services.ai_thesis import MaxTokensError
    assert issubclass(MaxTokensError, RuntimeError)


# =============================================================================
# TASK 7: Pydantic repair — string '10%' threshold is coerced to 0.10
# =============================================================================


def test_normalize_interpretation_repairs_string_percent_threshold():
    """'10%' string threshold must be converted to 0.10 and a warning logged."""
    result = _normalize_interpretation(
        {
            "labels": ["growth"],
            "monitorability": "high",
            "watch_hints": [
                {
                    "kind": "metric_threshold",
                    "metric": "revenue_growth_yoy",
                    "operator": ">=",
                    "threshold": "10%",
                    "rationale": "Must grow 10%.",
                }
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        }
    )
    metric_hint = next(
        (h for h in result["watch_hints"] if h.get("kind") == "metric_threshold"), None
    )
    assert metric_hint is not None, "metric_threshold hint was dropped"
    assert metric_hint["threshold"] == pytest.approx(0.10)


# =============================================================================
# TASK 8: Date injection — administration triggers warning not rewrite
# =============================================================================


def test_parse_draft_output_logs_warning_for_administration_reference(caplog):
    """After Task 8: 'administration' in output triggers a warning, not a rewrite."""
    import logging
    from app.services.ai_thesis import _parse_draft_output

    with caplog.at_level(logging.WARNING, logger="app.services.ai_thesis"):
        result = _parse_draft_output(
            {
                "why_own_it": "Tesla benefits if the new administration's EV credits stay.",
                "must_remain_true": "Federal administration support continues.",
                "what_would_change_my_mind": "If the administration reverses the policy.",
            },
            "TSLA",
        )
    # Text is NOT rewritten
    assert "administration" in result["why_own_it"].lower()
    # But a warning is logged
    assert any("administration" in r.message.lower() for r in caplog.records)
