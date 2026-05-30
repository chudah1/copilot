"""Regression test for the OpenAI reasoning provider.

prompt_cache_key was passed as a TOP-LEVEL kwarg to chat.completions.create(),
which older OpenAI SDKs reject ('unexpected keyword argument prompt_cache_key').
That silently killed the OpenAI tier of the decomposition fallback chain — any
thesis that fell through to OpenAI got no decomposition. It must go via
extra_body (forwarded straight to the API, regardless of SDK version).
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.reasoning.providers.openai_provider import OpenAIReasoningProvider
from app.services.reasoning.types import ReasoningRequest, ReasoningTaskType


@pytest.mark.asyncio
async def test_openai_provider_sends_cache_key_via_extra_body(monkeypatch):
    monkeypatch.setattr(
        "app.services.reasoning.providers.openai_provider.settings.openai_api_key",
        "test-key",
        raising=False,
    )

    captured: dict = {}
    content = json.dumps({
        "reason_type": "income",
        "monitorability": "high",
        "decomposition_confidence": 0.8,
        "claims": [
            {"claim_text": "Dividend keeps growing", "claim_type": "income", "confidence": 0.8, "entities": []}
        ],
    })
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return resp

    fake_client = MagicMock()
    fake_client.chat.completions.create = fake_create

    with patch("openai.AsyncOpenAI", return_value=fake_client):
        provider = OpenAIReasoningProvider()
        result = await provider.run(
            ReasoningRequest(
                task_type=ReasoningTaskType.DECOMPOSE_THESIS,
                thesis_id="t",
                user_id=f"unique-{id(captured)}",  # unique → cache miss → real call
                payload={
                    "ticker": "KO", "name": "Coca-Cola", "why_own_it": "brand",
                    "must_remain_true": "x", "what_would_change_my_mind": "y",
                },
            )
        )

    assert result.success is True
    # The cache key must NOT be a top-level kwarg (that's what crashed the SDK)...
    assert "prompt_cache_key" not in captured
    # ...it must be forwarded via extra_body.
    assert captured.get("extra_body", {}).get("prompt_cache_key")
