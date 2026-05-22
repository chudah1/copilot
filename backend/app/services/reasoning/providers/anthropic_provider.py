import json
import logging
import time
from hashlib import sha256

import anthropic

logger = logging.getLogger(__name__)

from app.config import settings
from app.services.reasoning.prompts import (
    DECOMPOSITION_JSON_SCHEMA,
    DECOMPOSITION_PROMPT_VERSION,
    DECOMPOSITION_SYSTEM_PROMPT,
    build_decomposition_prompt,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.simple_cache import TTLCache


class AnthropicReasoningProvider:
    name = "anthropic"
    model = settings.anthropic_model
    timeout_seconds = 60
    _cache = TTLCache(ttl_seconds=settings.llm_response_cache_ttl_seconds)

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        started = time.perf_counter()
        if request.task_type != ReasoningTaskType.DECOMPOSE_THESIS:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Unsupported task", False)
        if not settings.anthropic_api_key:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Anthropic API key not configured", False)
        try:
            cache_key = sha256(
                f"{self.name}:{self.model}:{DECOMPOSITION_PROMPT_VERSION}:{request.user_id}:{json.dumps(request.payload, sort_keys=True)}".encode("utf-8")
            ).hexdigest()
            cached = self._cache.get(cache_key)
            if cached is not None:
                latency = int((time.perf_counter() - started) * 1000)
                return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, cached, None, latency, None, True)

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            async with client.messages.stream(
                model=self.model,
                max_tokens=8000,
                tools=[
                    {
                        "name": "record_thesis_decomposition",
                        "description": "Return the thesis decomposition in the required structured schema.",
                        "input_schema": DECOMPOSITION_JSON_SCHEMA,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tool_choice={"type": "tool", "name": "record_thesis_decomposition"},
                system=[
                    {
                        "type": "text",
                        "text": DECOMPOSITION_SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": build_decomposition_prompt(request.payload)}],
                temperature=0,
                timeout=self.timeout_seconds,
            ) as stream:
                response = await stream.get_final_message()
            usage = response.usage
            logger.info(
                "Anthropic decomposition usage — input: %s, output: %s, cache_read: %s, cache_write: %s, stop_reason: %s",
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
                getattr(usage, "cache_read_input_tokens", 0),
                getattr(usage, "cache_creation_input_tokens", 0),
                response.stop_reason,
            )
            if response.stop_reason == "max_tokens":
                logger.warning("Anthropic hit max_tokens during decomposition — output may be truncated")
            raw = None
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    raw = getattr(block, "input", None)
                    break
            if raw is None:
                raise ValueError("Claude did not return a tool_use payload")
            # Only cache if claims were actually extracted — don't poison the
            # cache with an empty-claims response that might be a model fluke.
            if raw.get("claims"):
                self._cache.set(cache_key, raw)
            latency = int((time.perf_counter() - started) * 1000)
            logger.info("Anthropic decomposition completed in %d ms", latency)
            return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, raw, None, latency, None, True)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            logger.error("Anthropic decomposition failed after %d ms", latency)
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, latency, str(exc), True)
