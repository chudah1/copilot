import logging

from app.services.reasoning.normalizers import normalize_decomposition_output
from app.services.reasoning.providers import (
    AnthropicReasoningProvider,
    OpenAIReasoningProvider,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.validators import (
    output_needs_escalation,
    validate_decomposition_output,
)

logger = logging.getLogger(__name__)


class ThesisReasoningGateway:
    def __init__(self, providers: list | None = None):
        self.providers = providers or [
            OpenAIReasoningProvider(),
            AnthropicReasoningProvider(),
            # GeminiReasoningProvider(),  # Temporarily disabled due to timeout issues
        ]

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        if request.task_type == ReasoningTaskType.DECOMPOSE_THESIS:
            return await self._run_decomposition(request)
        return ReasoningResult(
            success=False,
            status="failed",
            provider=None,
            model=None,
            prompt_version=None,
            normalized_output=None,
            raw_output=None,
            confidence=None,
            latency_ms=None,
            failure_reason=f"Unsupported task type: {request.task_type}",
            retryable=False,
        )

    async def _run_decomposition(self, request: ReasoningRequest) -> ReasoningResult:
        last_failure: ReasoningResult | None = None
        original_text = str(request.payload.get("why_own_it", ""))

        for provider in self.providers:
            try:
                result = await provider.run(request)
            except Exception as exc:
                logger.exception("Reasoning provider %s raised an unhandled exception", getattr(provider, "name", "<unknown>"))
                last_failure = ReasoningResult(
                    success=False,
                    status="failed",
                    provider=getattr(provider, "name", None),
                    model=getattr(provider, "model", None),
                    prompt_version=None,
                    normalized_output=None,
                    raw_output=None,
                    confidence=None,
                    latency_ms=None,
                    failure_reason=str(exc),
                    retryable=True,
                )
                continue
            if not result.success:
                logger.warning("Reasoning provider %s failed: %s", provider.name, result.failure_reason)
                last_failure = result
                continue

            normalized_output = normalize_decomposition_output(result.raw_output or {})
            valid, validation_error = validate_decomposition_output(
                normalized_output,
                original_text=original_text,
            )
            if not valid:
                last_failure = ReasoningResult(
                    success=False,
                    status="failed",
                    provider=result.provider,
                    model=result.model,
                    prompt_version=result.prompt_version,
                    normalized_output=normalized_output,
                    raw_output=result.raw_output,
                    confidence=normalized_output.get("decomposition_confidence"),
                    latency_ms=result.latency_ms,
                    failure_reason=validation_error,
                    retryable=True,
                )
                continue

            escalate, escalation_reason = output_needs_escalation(
                normalized_output,
                original_text=original_text,
            )
            if escalate:
                last_failure = ReasoningResult(
                    success=False,
                    status="failed",
                    provider=result.provider,
                    model=result.model,
                    prompt_version=result.prompt_version,
                    normalized_output=normalized_output,
                    raw_output=result.raw_output,
                    confidence=normalized_output.get("decomposition_confidence"),
                    latency_ms=result.latency_ms,
                    failure_reason=escalation_reason,
                    retryable=True,
                )
                continue

            result.normalized_output = normalized_output
            result.confidence = normalized_output.get("decomposition_confidence")
            result.status = "success"
            return result

        return ReasoningResult(
            success=False,
            status="pending" if (last_failure is None or last_failure.retryable) else "failed",
            provider=last_failure.provider if last_failure else None,
            model=last_failure.model if last_failure else None,
            prompt_version=last_failure.prompt_version if last_failure else None,
            normalized_output=None,
            raw_output=last_failure.raw_output if last_failure else None,
            confidence=last_failure.confidence if last_failure else None,
            latency_ms=last_failure.latency_ms if last_failure else None,
            failure_reason=(last_failure.failure_reason if last_failure else "All providers failed or returned unusable output."),
            retryable=last_failure.retryable if last_failure else True,
        )
