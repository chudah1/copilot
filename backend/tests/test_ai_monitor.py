import pytest
from unittest.mock import patch

from app.services.ai_monitor import (
    _build_classification_prompt,
    _normalize_analysis_text,
    classify_event,
    _parse_classification_response,
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
    assert "started from a story or tip" in prompt


async def test_classify_event_uses_profile_aware_fallback_when_no_key():
    with patch("app.services.ai_monitor.settings") as mock_settings:
        mock_settings.anthropic_api_key = None
        result = await classify_event(
            why_own_it="AI demand should keep the story alive",
            must_remain_true=None,
            what_would_change_my_mind=None,
            ai_summary=None,
            event_description="Orders slowed this quarter.",
            investor_profile="hearsay_driven",
        )

    assert result is not None
    assert result.severity == "warning"
    assert "original story" in result.analysis


def test_normalize_analysis_text_adds_decision_ready_structure():
    result = _normalize_analysis_text(
        event_description="Management cut demand guidance.",
        analysis="This weakens the demand case. Orders may not be as durable as expected.",
        severity="warning",
        investor_profile="thesis_driven",
    )
    assert result.startswith("Management cut demand guidance.")
    assert "assumption" in result.lower() or "demand" in result.lower()
    assert "review" in result.lower()


def test_normalize_analysis_text_uses_hearsay_specific_decision_pressure():
    result = _normalize_analysis_text(
        event_description="Channel checks point to weaker orders.",
        analysis="",
        severity="warning",
        investor_profile="hearsay_driven",
    )
    assert "Channel checks point to weaker orders." in result
    assert "story" in result.lower()
    assert "review" in result.lower()
