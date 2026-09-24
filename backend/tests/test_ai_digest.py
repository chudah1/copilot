from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_digest import (
    _build_digest_prompt,
    _fallback_digest,
    _parse_digest_response,
    generate_digest_content,
)
from app.services.ai_utils import strip_code_fences as _strip_code_fences


def test_strip_code_fences_handles_fenced_json():
    text = '```json\n{"insights":[],"portfolio_warnings":[]}\n```'
    assert _strip_code_fences(text) == '{"insights":[],"portfolio_warnings":[]}'


def test_build_digest_prompt_includes_sections():
    prompt = _build_digest_prompt(
        holdings_with_theses=[
            {
                "ticker": "AAPL",
                "name": "Apple",
                "why_own_it": "Resilient ecosystem demand.",
                "must_remain_true": "Demand stays strong.",
                "what_would_change_my_mind": "Demand weakens.",
            }
        ],
        events=[{"ticker": "AAPL", "severity": "warning", "title": "Price moved", "summary": "Shares fell 8%."}],
        observations={"stable_holdings": [{"ticker": "MSFT", "stale": False}], "missing_theses": ["TSLA"]},
    )
    assert "Resilient ecosystem demand." in prompt
    assert "[WARNING] AAPL: Price moved" in prompt
    assert "- MSFT" in prompt
    assert "Positions without theses: TSLA" in prompt


def test_parse_digest_response_accepts_valid_payload():
    payload = _parse_digest_response(
        '{"insights":[{"ticker":"AAPL","type":"event","headline":"Moved","rationale":"Review it."}],"portfolio_warnings":["Watch concentration."]}'
    )
    assert payload["insights"][0]["type"] == "event"
    assert payload["portfolio_warnings"] == ["Watch concentration."]


def test_parse_digest_response_rejects_invalid_insight_type():
    with pytest.raises(ValueError):
        _parse_digest_response(
            '{"insights":[{"ticker":"AAPL","type":"unknown","headline":"Moved","rationale":"Review it."}],"portfolio_warnings":[]}'
        )


async def test_generate_digest_content_falls_back_without_api_key():
    holdings = [{"ticker": "AAPL", "name": "Apple"}]
    events = [{"ticker": "AAPL", "title": "Price moved", "summary": "Shares fell 8%."}]
    observations = {"stable_holdings": [{"ticker": "MSFT", "stale": True}], "missing_theses": ["TSLA"]}

    with patch("app.services.ai_digest.settings") as mock_settings:
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = None
        digest = await generate_digest_content(holdings, events, observations)

    assert digest == _fallback_digest(holdings, events, observations)


async def test_generate_digest_content_falls_back_on_malformed_model_response():
    holdings = [{"ticker": "AAPL", "name": "Apple"}]
    events = [{"ticker": "AAPL", "severity": "warning", "title": "Price moved", "summary": "Shares fell 8%."}]
    observations = {}
    bad_response = SimpleNamespace(content=[SimpleNamespace(text='{"insights":"bad","portfolio_warnings":[]}')])
    mock_client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=bad_response)))

    with patch("app.services.ai_digest.settings") as mock_settings:
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = "test-key"
        with patch("app.services.ai_digest.anthropic.AsyncAnthropic", return_value=mock_client):
            digest = await generate_digest_content(holdings, events, observations)

    assert digest == _fallback_digest(holdings, events, observations)
