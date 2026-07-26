import pytest
from unittest.mock import patch

from app.services.ai_monitor import (
    _CLASSIFY_SYSTEM,
    _build_classification_prompt,
    _normalize_classification_result,
    _normalize_analysis_text,
    classify_event,
    _parse_classification_response,
    ClassificationResult,
)
from app.services.ai_utils import strip_code_fences as _strip_code_fences


def test_strip_code_fences_handles_plain_json():
    text = '{"severity":"warning","analysis":"Review this."}'
    assert _strip_code_fences(text) == text


def test_strip_code_fences_handles_fenced_json():
    text = '```json\n{"severity":"warning","analysis":"Review this."}\n```'
    assert _strip_code_fences(text) == '{"severity":"warning","analysis":"Review this."}'


def test_parse_classification_response_accepts_valid_payload():
    result = _parse_classification_response('{"severity":"info","analysis":"All clear."}')
    assert result.severity == "info"
    assert result.analysis == "All clear."
    # direction is optional — defaults to empty string when the LLM omits it.
    assert result.direction == ""


def test_parse_classification_response_extracts_valid_direction():
    result = _parse_classification_response(
        '{"severity":"info","direction":"supports","analysis":"Services beat pillar."}'
    )
    assert result.direction == "supports"


def test_parse_classification_response_ignores_bogus_direction():
    # Model garbage — treat as if it wasn't emitted at all. Downstream
    # determine_verdict falls back to severity-only logic.
    result = _parse_classification_response(
        '{"severity":"info","direction":"kinda-supportive","analysis":"Mixed read."}'
    )
    assert result.direction == ""


def test_parse_classification_response_rejects_invalid_severity():
    with pytest.raises(ValueError):
        _parse_classification_response('{"severity":"unknown","analysis":"Nope."}')


def test_build_classification_prompt_fills_fallback_text():
    prompt = _build_classification_prompt(
        why_own_it="Demand stays strong",
        must_remain_true=None,
        what_would_change_my_mind=None,
        ai_summary=None,
        event_description="Revenue missed expectations.",
    )
    assert "Demand stays strong" in prompt
    assert "Not specified" in prompt
    assert "Not available" in prompt
    assert "Revenue missed expectations." in prompt


def test_build_classification_prompt_includes_profile_guidance():
    prompt = _build_classification_prompt(
        why_own_it="Datacenter demand stays strong",
        must_remain_true="Customers keep spending on AI infrastructure",
        what_would_change_my_mind="Orders weaken for multiple quarters",
        ai_summary="Demand-led compounder",
        event_description="Management cut demand guidance.",
        investor_profile="hearsay_driven",
    )
    assert "Investor profile: hearsay_driven" in prompt
    assert "started from a tip or theme" in prompt


def test_classify_system_forbids_positive_thesis_breaking():
    assert 'Positive or thesis-confirming events are never "thesis_breaking"' in _CLASSIFY_SYSTEM


def test_classify_system_requires_direct_user_facing_language():
    assert "Lead with the conclusion" in _CLASSIFY_SYSTEM
    assert '"This evidence"' in _CLASSIFY_SYSTEM
    assert '"supports the thesis"' in _CLASSIFY_SYSTEM
    assert "Do not write the action" in _CLASSIFY_SYSTEM


async def test_classify_event_stays_quiet_when_no_classifier_is_available():
    with patch("app.services.ai_monitor.settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        mock_settings.openai_api_key = None
        result = await classify_event(
            why_own_it="AI demand should keep the story alive",
            must_remain_true=None,
            what_would_change_my_mind=None,
            ai_summary=None,
            event_description="Orders slowed this quarter.",
            investor_profile="hearsay_driven",
        )

    assert result is None


def test_normalize_classification_result_caps_supportive_thesis_breaking():
    normalized = _normalize_classification_result(
        ClassificationResult(
            severity="thesis_breaking",
            direction="supports",
            analysis="Record bookings support the demand pillar.",
        )
    )

    assert normalized.severity == "warning"
    assert normalized.direction == "supports"
    assert normalized.analysis == "Record bookings support the demand pillar."


def test_normalize_classification_result_leaves_threatening_breakages_alone():
    normalized = _normalize_classification_result(
        ClassificationResult(
            severity="thesis_breaking",
            direction="threatens",
            analysis="Orders collapsed below the stated floor.",
        )
    )

    assert normalized.severity == "thesis_breaking"
    assert normalized.direction == "threatens"


def test_normalize_analysis_text_removes_meta_language_and_repeated_action():
    result = _normalize_analysis_text(
        event_description=(
            "ServiceNow is projected to grow subscription revenue 21% to 21.5%, "
            "supported by improving demand."
        ),
        analysis=(
            "That range, if it prints, would support the demand story the thesis "
            "requires and suggests AI-driven upsell is not yet stalling. "
            "No rush, keep watching for now."
        ),
        severity="info",
        investor_profile="thesis_driven",
    )
    assert result == (
        "ServiceNow is projected to grow subscription revenue 21% to 21.5%, "
        "supported by improving demand. No action needed."
    )
    assert "thesis" not in result.lower()
    assert "story" not in result.lower()
    assert "suggests" not in result.lower()
    assert "no rush" not in result.lower()


def test_normalize_analysis_text_keeps_concrete_read_and_uses_direct_action():
    result = _normalize_analysis_text(
        event_description=(
            "ServiceNow shares fell 36%, while subscription growth remained solid."
        ),
        analysis=(
            "This evidence threatens your reason. The market is worried about AI "
            "competition, although reported subscription growth remains solid."
        ),
        severity="warning",
        investor_profile="thesis_driven",
    )
    assert result == (
        "The market is worried about AI competition, although reported subscription "
        "growth remains solid. Review this position."
    )
    assert "this evidence" not in result.lower()
    assert "pillar" not in result.lower()
    assert "background noise" not in result.lower()


def test_normalize_analysis_text_preserves_two_direct_sentences():
    result = _normalize_analysis_text(
        event_description="ServiceNow reported quarterly results.",
        analysis=(
            "ServiceNow's customer demand is holding up. "
            "Subscription revenue grew 22%."
        ),
        severity="info",
        investor_profile="thesis_driven",
    )
    assert result == (
        "ServiceNow's customer demand is holding up. "
        "Subscription revenue grew 22%. No action needed."
    )


def test_normalize_analysis_text_uses_direct_breaking_action():
    result = _normalize_analysis_text(
        event_description="ServiceNow reported quarterly results.",
        analysis=(
            "Subscription growth has stayed below 15% for two quarters. "
            "The investor's minimum was 20%."
        ),
        severity="thesis_breaking",
        investor_profile="thesis_driven",
    )
    assert result.endswith("A decision is needed now.")
