"""Regression tests for the OpenAI reasoning provider.

prompt_cache_key was passed as a TOP-LEVEL kwarg to chat.completions.create(),
which older OpenAI SDKs reject ('unexpected keyword argument prompt_cache_key').
That silently killed the OpenAI tier of the decomposition fallback chain — any
thesis that fell through to OpenAI got no decomposition. It must go via
extra_body (forwarded straight to the API, regardless of SDK version).

The signal_config_json schema previously collapsed to a closed empty object
under strict mode, which meant GPT-* could not populate metric / operator /
threshold / threshold_pct / segment / topic — silently destroying
config_population scores on every quantitative thesis family. The strict
schema must keep those fields and make them nullable instead.
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


def _signal_config_schema():
    """Pull the signal_config_json subschema out of the provider's strict
    response schema so tests don't depend on the full schema layout."""
    provider = OpenAIReasoningProvider()
    schema = provider._response_schema()
    return (
        schema["properties"]["claims"]["items"]
        ["properties"]["entities"]["items"]
        ["properties"]["signals"]["items"]
        ["properties"]["signal_config_json"]
    )


def test_strict_signal_config_schema_keeps_metric_threshold_topic_fields():
    """The strict-mode adaptation must not destroy the populated-config fields,
    or every quantitative thesis loses its threshold configuration."""
    cfg = _signal_config_schema()
    properties = cfg.get("properties", {})
    for field in ("metric", "operator", "threshold", "threshold_pct", "segment", "topic"):
        assert field in properties, f"signal_config_json schema missing '{field}' — populated configs will be impossible"


def test_strict_signal_config_schema_allows_null_for_every_field():
    """OpenAI strict mode requires every property in `required`, so optional
    fields must be expressed as nullable types instead of omitted."""
    cfg = _signal_config_schema()
    required = set(cfg.get("required", []))
    properties = cfg.get("properties", {})
    for field, definition in properties.items():
        assert field in required, f"strict mode requires '{field}' to be in required"
        type_value = definition.get("type")
        if isinstance(type_value, list):
            assert "null" in type_value, f"'{field}' must allow null in strict mode"
        else:
            assert type_value is None or type_value == "null", (
                f"'{field}' has non-nullable type {type_value!r}; strict mode "
                "requires nullable since the field is logically optional"
            )


def test_strict_signal_config_schema_operator_enum_includes_null():
    """When the operator field is nullable, OpenAI strict mode requires `null`
    to also be a valid enum value."""
    cfg = _signal_config_schema()
    operator_def = cfg.get("properties", {}).get("operator", {})
    if "enum" not in operator_def:
        return  # No enum constraint; nothing to check.
    assert None in operator_def["enum"], (
        "operator enum must include null when the type allows null, or strict "
        "mode will reject any output that leaves operator unset"
    )


def test_strict_signal_config_schema_disallows_additional_properties():
    """Strict mode requires additionalProperties: false."""
    cfg = _signal_config_schema()
    assert cfg.get("additionalProperties") is False
