import pytest

from app.services.ai_monitor import (
    _build_classification_prompt,
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
