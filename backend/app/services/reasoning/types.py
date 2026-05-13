from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class ReasoningTaskType(str, Enum):
    DECOMPOSE_THESIS = "decompose_thesis"
    EVALUATE_EVIDENCE = "evaluate_evidence"


@dataclass
class ReasoningRequest:
    task_type: ReasoningTaskType
    payload: dict[str, Any]
    user_id: str | None = None
    thesis_id: str | None = None


@dataclass
class ReasoningResult:
    success: bool
    status: str
    provider: str | None
    model: str | None
    prompt_version: str | None
    normalized_output: dict[str, Any] | None
    raw_output: dict[str, Any] | None
    confidence: float | None
    latency_ms: int | None
    failure_reason: str | None
    retryable: bool = True


class ReasoningProvider(Protocol):
    name: str

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        ...
