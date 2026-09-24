import logging

from app.services.reasoning.complexity import classify_complexity
from app.services.reasoning.normalizers import normalize_decomposition_output
from app.services.reasoning.providers import (
    AnthropicReasoningProvider,
    OpenAILunaProvider,
    OpenAIReasoningProvider,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.validators import (
    output_needs_escalation,
    prune_invalid_mappings,
    validate_decomposition_output,
)

logger = logging.getLogger(__name__)

# Cheap tier: Luna first for high-volume work, then Terra if its output needs
# escalation. Anthropic remains an independent final fallback.
_CHEAP_PROVIDERS = [OpenAILunaProvider(), OpenAIReasoningProvider(), AnthropicReasoningProvider()]
# Expensive tier: Terra first for rich theses with explicit thresholds,
# competitors, and all fields filled.
_EXPENSIVE_PROVIDERS = [OpenAIReasoningProvider(), AnthropicReasoningProvider()]


class ThesisReasoningGateway:
    def __init__(self, providers: list | None = None):
        # When providers is explicitly passed (e.g. in tests), use them directly.
        # Otherwise, complexity routing selects the tier per-request.
        self._override_providers = providers

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

    def _select_providers(self, payload: dict) -> list:
        if self._override_providers is not None:
            return self._override_providers
        tier = classify_complexity(payload)
        providers = _CHEAP_PROVIDERS if tier == "cheap" else _EXPENSIVE_PROVIDERS
        logger.debug("Complexity tier '%s' selected for thesis decomposition", tier)
        return providers

    async def _run_decomposition(self, request: ReasoningRequest) -> ReasoningResult:
        last_failure: ReasoningResult | None = None
        original_text = str(request.payload.get("why_own_it", ""))
        providers = self._select_providers(request.payload)

        for provider in providers:
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
                if validation_error and "not a sensible match" in validation_error:
                    sanitized_output, removed = prune_invalid_mappings(normalized_output)
                    sanitized_valid, sanitized_error = validate_decomposition_output(
                        sanitized_output,
                        original_text=original_text,
                    )
                    if sanitized_valid and sanitized_output.get("claims"):
                        logger.warning(
                            "Provider %s produced partially invalid decomposition; dropped %d invalid mappings: %s",
                            provider.name,
                            len(removed),
                            "; ".join(removed),
                        )
                        normalized_output = sanitized_output
                        validation_error = None
                        valid = True
                    else:
                        validation_error = sanitized_error or validation_error

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
                logger.warning(
                    "Provider %s escalation (%s) — raw_output: %s",
                    provider.name,
                    escalation_reason,
                    result.raw_output,
                )
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
