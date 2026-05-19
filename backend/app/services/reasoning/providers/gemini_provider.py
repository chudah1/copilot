import asyncio
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


class GeminiReasoningProvider:
    name = "gemini"
    model = "gemini-2.5-flash"
    timeout_seconds = 30
    _cache = TTLCache(ttl_seconds=settings.llm_response_cache_ttl_seconds)

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        started = time.perf_counter()
        if request.task_type != ReasoningTaskType.DECOMPOSE_THESIS:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Unsupported task", False)
        if not settings.gemini_api_key:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Gemini API key not configured", False)
        try:
            from google import genai
        except ImportError:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Gemini SDK not installed", False)
        try:
            cache_key = sha256(
                f"{self.name}:{self.model}:{DECOMPOSITION_PROMPT_VERSION}:{request.user_id}:{json.dumps(request.payload, sort_keys=True)}".encode("utf-8")
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached is not None:
                latency = int((time.perf_counter() - started) * 1000)
                return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, cached, None, latency, None, True)

            client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options={
                    "timeout": self.timeout_seconds,
                    # Retry transient provider-side failures (429/5xx). Timeouts are handled below.
                    "retry_options": {
                        "attempts": 2,
                        "initial_delay": 0.5,
                        "max_delay": 4.0,
                        "exp_base": 2.0,
                        "jitter": 0.2,
                        "http_status_codes": [429, 500, 502, 503, 504],
                    },
                },
            )

            async def _call_once():
                return await client.aio.models.generate_content(
                    model=self.model,
                    contents=build_decomposition_prompt(request.payload),
                    config={
                        "system_instruction": DECOMPOSITION_SYSTEM_PROMPT,
                        "response_mime_type": "application/json",
                        "response_json_schema": DECOMPOSITION_JSON_SCHEMA,
                        "temperature": 0,
                        "max_output_tokens": 1800,
                    },
                )

            try:
                response = await _call_once()
            except asyncio.TimeoutError:
                # One retry: Gemini can be spiky; retry once before failing routing.
                response = await _call_once()
            text = getattr(response, "text", None) or "{}"
            raw = json.loads(text)
            self._cache.set(cache_key, raw)
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, raw, None, latency, None, True)
        except asyncio.TimeoutError:
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(
                False,
                "failed",
                self.name,
                self.model,
                DECOMPOSITION_PROMPT_VERSION,
                None,
                None,
                None,
                latency,
                f"Timed out after {self.timeout_seconds} seconds",
                True,
            )
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, latency, str(exc), True)
