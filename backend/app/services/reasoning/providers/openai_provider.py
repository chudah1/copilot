import asyncio
import copy
import json
import time

from app.config import settings
from app.services.reasoning.prompts import (
    DECOMPOSITION_JSON_SCHEMA,
    DECOMPOSITION_PROMPT_VERSION,
    build_decomposition_prompt,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType


class OpenAIReasoningProvider:
    name = "openai"
    model = "gpt-4.1-mini"
    timeout_seconds = 20

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
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "thesis_decomposition",
                            "strict": True,
                            "schema": self._response_schema(),
                        },
                    },
                    messages=[
                        {"role": "system", "content": "Produce only the structured decomposition that matches the provided JSON schema."},
                        {"role": "user", "content": build_decomposition_prompt(request.payload)},
                    ],
                ),
                timeout=self.timeout_seconds,
            )
            text = response.choices[0].message.content or "{}"
            raw = json.loads(text)
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(True, "success", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, raw, None, latency, None, True)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ReasoningResult(False, "failed", self.name, self.model, DECOMPOSITION_PROMPT_VERSION, None, None, None, latency, str(exc), True)
