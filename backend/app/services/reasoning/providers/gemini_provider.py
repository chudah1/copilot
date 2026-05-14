import asyncio
import json
import time

from app.config import settings
from app.services.reasoning.prompts import (
    DECOMPOSITION_JSON_SCHEMA,
    DECOMPOSITION_PROMPT_VERSION,
    build_decomposition_prompt,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType


class GeminiReasoningProvider:
    name = "gemini"
    model = "gemini-2.5-flash"
    timeout_seconds = 30

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
            client = genai.Client(api_key=settings.gemini_api_key)
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=self.model,
                    contents=build_decomposition_prompt(request.payload),
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": DECOMPOSITION_JSON_SCHEMA,
                    },
                ),
                timeout=self.timeout_seconds,
            )
            text = getattr(response, "text", None) or "{}"
            raw = json.loads(text)
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
