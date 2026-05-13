import asyncio
import json
import time

import anthropic

from app.config import settings
from app.services.reasoning.prompts import (
    DECOMPOSITION_JSON_SCHEMA,
    DECOMPOSITION_PROMPT_VERSION,
    build_decomposition_prompt,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType


class AnthropicReasoningProvider:
    name = "anthropic"
    model = "claude-sonnet-4-20250514"
    timeout_seconds = 20

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        started = time.perf_counter()
        if request.task_type != ReasoningTaskType.DECOMPOSE_THESIS:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Unsupported task", False)
        if not settings.anthropic_api_key:
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, 0, "Anthropic API key not configured", False)
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self.model,
                    max_tokens=1800,
                    tools=[
                        {
                            "name": "record_thesis_decomposition",
                            "description": "Return the thesis decomposition in the required structured schema.",
                            "input_schema": DECOMPOSITION_JSON_SCHEMA,
                        }
                    ],
                    tool_choice={"type": "tool", "name": "record_thesis_decomposition"},
                    messages=[{"role": "user", "content": build_decomposition_prompt(request.payload)}],
                ),
                timeout=self.timeout_seconds,
            )
            raw = None
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    raw = getattr(block, "input", None)
                    break
            if raw is None:
                raise ValueError("Claude did not return a tool_use payload")
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, raw, None, latency, None, True)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, latency, str(exc), True)
