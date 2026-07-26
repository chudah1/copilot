from app.services.ai_digest import DIGEST_PROMPT, _fallback_digest
from app.services.ai_thesis import (
    COUNTER_THESIS_PROMPT,
    DRAFT_THESIS_PROMPT,
    SYNTHESIS_PROMPT,
    THESIS_ASSIST_FROM_BLANK_PROMPT,
    THESIS_PROMPT,
    _STRESS_TEST_PROMPT,
    _fallback_counter_thesis,
    _fallback_stress_test,
)
from app.services.earnings_review import _EARNINGS_REVIEW_PROMPT
from app.services.edgar_extractor import _EXTRACTION_PROMPT
from app.services.news_watch import _JUDGE_SYSTEM
from app.services.reasoning.prompts import DECOMPOSITION_SYSTEM_PROMPT
from app.services.signal_matching import _build_event_decision, _build_event_implication
from app.services.thesis_relevance_filter import _RELEVANCE_PROMPT


def test_user_facing_model_prompts_require_direct_language():
    prompts = [
        COUNTER_THESIS_PROMPT,
        DRAFT_THESIS_PROMPT,
        SYNTHESIS_PROMPT,
        THESIS_ASSIST_FROM_BLANK_PROMPT,
        THESIS_PROMPT,
        _STRESS_TEST_PROMPT,
        DIGEST_PROMPT,
        _EARNINGS_REVIEW_PROMPT,
        DECOMPOSITION_SYSTEM_PROMPT,
        _EXTRACTION_PROMPT,
        _JUDGE_SYSTEM,
        _RELEVANCE_PROMPT,
    ]
    for prompt in prompts:
        assert "Lead with the conclusion" in prompt
        assert "Name the exact" in prompt


def test_counter_thesis_fallback_avoids_meta_investment_language():
    result = _fallback_counter_thesis(
        why_own_it="Cloud and AI revenue keep growing.",
        must_remain_true="Cloud revenue stays above 15% growth.",
        what_would_change_my_mind="Growth falls below 10%.",
        ai_summary=None,
        ticker="MSFT",
    )
    copy = " ".join(
        [
            result.bear_case,
            *result.key_risks,
            *result.blind_spots,
            *result.suggested_additions,
        ]
    ).lower()
    assert "story" not in copy
    assert "bull case" not in copy
    assert "thesis" not in copy


def test_stress_test_fallback_avoids_meta_investment_language():
    result = _fallback_stress_test("NVDA", "AI demand keeps revenue growing.")
    copy = " ".join(
        [
            result.bear_case,
            *result.key_risks,
            *(item for group in result.risk_groups for item in group.items),
            *result.blind_spots,
            *result.what_to_watch,
            *(signal.rationale for signal in result.candidate_signals),
        ]
    ).lower()
    assert "bull case" not in copy
    assert "growth case" not in copy
    assert "thesis" not in copy


def test_digest_fallback_states_what_happened_instead_of_declaring_thesis_intact():
    digest = _fallback_digest(
        [{"ticker": "MSFT", "name": "Microsoft"}],
        [],
        {"stable_holdings": [{"ticker": "MSFT", "stale": False}]},
    )
    stable = digest["insights"][0]
    assert stable["rationale"] == "No material company news or monitored changes were found."
    assert "thesis" not in stable["rationale"].lower()


def test_event_explanation_uses_plain_status_and_action():
    assert (
        _build_event_implication(
            claim_text=None,
            signal_label="NOW subscription revenue growth",
            severity="info",
            verdict="supports",
        )
        == "NOW subscription revenue growth is holding up."
    )
    assert (
        _build_event_implication(
            claim_text=None,
            signal_label="NOW subscription revenue growth",
            severity="warning",
            verdict="threatens",
        )
        == "NOW subscription revenue growth is weakening."
    )
    assert (
        _build_event_decision(
            severity="warning",
            verdict="review",
            investor_profile="thesis_driven",
        )
        == "Review this position."
    )
    assert (
        _build_event_decision(
            severity="thesis_breaking",
            verdict="threatens",
            investor_profile="hearsay_driven",
        )
        == "A decision is needed now."
    )
