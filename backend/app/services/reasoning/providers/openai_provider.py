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
    model = "gpt-4.1-mini"
    timeout_seconds = 60
    _cache = TTLCache(ttl_seconds=settings.llm_response_cache_ttl_seconds)

    def _response_schema(self) -> dict:
        # OpenAI Structured Outputs is stricter than our cross-provider schema:
        # nested objects cannot stay open-ended or partially optional. For the
        # OpenAI adapter, we collapse signal_config_json to a closed empty
        # object and let richer providers supply more detailed configs.
        schema = copy.deepcopy(DECOMPOSITION_JSON_SCHEMA)
        signal_config_json = (
            schema["properties"]["claims"]["items"]["properties"]["entities"]["items"]["properties"]["signals"]["items"]["properties"]["signal_config_json"]
        )
        signal_config_json["properties"] = {}
        signal_config_json["required"] = []
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
            response = await client.chat.completions.create(
                model=self.model,
                prompt_cache_key=settings.openai_prompt_cache_key,
                prompt_cache_retention=settings.openai_prompt_cache_retention,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "thesis_decomposition",
                        "strict": True,
                        "schema": self._response_schema(),
                    },
                },
                messages=[
                    {"role": "system", "content": DECOMPOSITION_SYSTEM_PROMPT},
                    {"role": "user", "content": build_decomposition_prompt(request.payload)},
                ],
                temperature=0,
                timeout=self.timeout_seconds,
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


class Gpt4oMiniProvider(OpenAIReasoningProvider):
    """Cheaper OpenAI tier for simple theses — routed by complexity classifier."""
    name = "openai_mini"
    model = "gpt-4o-mini"
