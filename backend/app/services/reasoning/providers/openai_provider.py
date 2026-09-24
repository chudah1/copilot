import asyncio
import copy
import json
import time
from hashlib import sha256

from app.config import settings
from app.services.reasoning.prompts import (
    DECOMPOSITION_JSON_SCHEMA,
    DECOMPOSITION_PROMPT_VERSION,
    DECOMPOSITION_SYSTEM_PROMPT,
    build_decomposition_prompt,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.simple_cache import TTLCache


class OpenAIReasoningProvider:
    name = "openai"
    model = settings.openai_reasoning_model
    timeout_seconds = 60
    schema_strict = True
    temperature: float | None = None  # Omit temperature for newer reasoning families that only support the default.
    _cache = TTLCache(ttl_seconds=settings.llm_response_cache_ttl_seconds)

    def _response_schema(self) -> dict:
        if not self.schema_strict:
            return DECOMPOSITION_JSON_SCHEMA
        # OpenAI Structured Outputs strict mode requires every key in properties
        # to appear in `required`. Optional fields are expressed as nullable
        # types instead of omission. Previously we collapsed signal_config_json
        # to a closed empty object — which silently destroyed every quantitative
        # threshold (metric/operator/threshold/threshold_pct/segment/topic
        # could not be emitted at all). Keep the fields and make them nullable.
        schema = copy.deepcopy(DECOMPOSITION_JSON_SCHEMA)
        signal_config_json = (
            schema["properties"]["claims"]["items"]["properties"]["entities"]["items"]["properties"]["signals"]["items"]["properties"]["signal_config_json"]
        )
        original_properties = signal_config_json.get("properties", {}) or {}
        nullable_properties: dict = {}
        for field, definition in original_properties.items():
            adapted = copy.deepcopy(definition)
            original_type = adapted.get("type")
            if isinstance(original_type, str):
                adapted["type"] = [original_type, "null"]
            elif isinstance(original_type, list) and "null" not in original_type:
                adapted["type"] = list(original_type) + ["null"]
            # If the field is an enum, strict mode requires `null` to be a
            # legal enum value when the type allows null.
            if "enum" in adapted and None not in adapted["enum"]:
                adapted["enum"] = list(adapted["enum"]) + [None]
            nullable_properties[field] = adapted
        signal_config_json["properties"] = nullable_properties
        signal_config_json["required"] = list(nullable_properties.keys())
        signal_config_json["additionalProperties"] = False
        return schema

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        started = time.perf_counter()
        if request.task_type != ReasoningTaskType.DECOMPOSE_THESIS:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Unsupported task", False)
        if not settings.openai_api_key:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "OpenAI API key not configured", False)
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "OpenAI SDK not installed", False)
        try:
            cache_key = sha256(
                f"{self.name}:{self.model}:{DECOMPOSITION_PROMPT_VERSION}:{request.user_id}:{json.dumps(request.payload, sort_keys=True)}".encode("utf-8")
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached is not None:
                latency = int((time.perf_counter() - started) * 1000)
                return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, cached, None, latency, None, True)

            client = AsyncOpenAI(api_key=settings.openai_api_key)
            extra: dict = {}
            if self.temperature is not None:
                extra["temperature"] = self.temperature
            response = await client.chat.completions.create(
                model=self.model,
                # Reasoning tokens count against this budget. Leave enough
                # room for the strict decomposition payload after reasoning.
                max_completion_tokens=4096,
                # Pass prompt-cache fields via extra_body so the call works across
                # OpenAI SDK versions (older SDKs reject these as top-level kwargs;
                # extra_body forwards them straight to the API).
                extra_body={
                    "prompt_cache_key": settings.openai_prompt_cache_key,
                    "prompt_cache_retention": settings.openai_prompt_cache_retention,
                    "reasoning_effort": "low",
                },
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "thesis_decomposition",
                        "strict": self.schema_strict,
                        "schema": self._response_schema(),
                    },
                },
                messages=[
                    {"role": "system", "content": DECOMPOSITION_SYSTEM_PROMPT},
                    {"role": "user", "content": build_decomposition_prompt(request.payload)},
                ],
                timeout=self.timeout_seconds,
                **extra,
            )
            text = response.choices[0].message.content or "{}"
            raw = json.loads(text)
            # Only cache if claims were actually extracted — don't poison the
            # cache with an empty-claims response that might be a model fluke.
            if raw.get("claims"):
                self._cache.set(cache_key, raw)
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, raw, None, latency, None, True)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, latency, str(exc), True)


class OpenAILunaProvider(OpenAIReasoningProvider):
    """Fast OpenAI tier for simple, high-volume thesis decomposition."""
    name = "openai_luna"
    model = settings.openai_fast_model


class Gpt4oMiniProvider(OpenAILunaProvider):
    """Compatibility alias for eval tooling that imports the old class name."""
