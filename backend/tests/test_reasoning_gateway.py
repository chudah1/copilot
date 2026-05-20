from app.services.reasoning.gateway import ThesisReasoningGateway
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType


class StubProvider:
    def __init__(self, name: str, result: ReasoningResult):
        self.name = name
        self._result = result

    async def run(self, request: ReasoningRequest) -> ReasoningResult:
        return self._result


def _request(why_own_it: str = "Revenue should keep growing.") -> ReasoningRequest:
    return ReasoningRequest(
        task_type=ReasoningTaskType.DECOMPOSE_THESIS,
        payload={
            "ticker": "AAPL",
            "name": "Apple Inc",
            "why_own_it": why_own_it,
            "must_remain_true": None,
            "what_would_change_my_mind": None,
        },
    )


async def test_gateway_stops_on_first_successful_provider():
    gateway = ThesisReasoningGateway(
        providers=[
            StubProvider(
                "openai",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="openai",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "medium",
                        "decomposition_confidence": 0.8,
                        "claims": [{"claim_text": "Revenue remains healthy.", "claim_type": "growth", "confidence": 0.8, "entities": []}],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            )
        ]
    )

    result = await gateway.run(_request())
    assert result.success is True
    assert result.provider == "openai"
    assert result.normalized_output is not None


async def test_gateway_escalates_when_first_provider_returns_weak_output():
    gateway = ThesisReasoningGateway(
        providers=[
            StubProvider(
                "openai",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="openai",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "medium",
                        "decomposition_confidence": 0.2,
                        "claims": [],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            ),
            StubProvider(
                "anthropic",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="anthropic",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "medium",
                        "decomposition_confidence": 0.8,
                        "claims": [{"claim_text": "Revenue remains healthy.", "claim_type": "growth", "confidence": 0.8, "entities": []}],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            ),
        ]
    )

    result = await gateway.run(_request())
    assert result.success is True
    assert result.provider == "anthropic"


async def test_gateway_returns_pending_when_all_providers_fail():
    gateway = ThesisReasoningGateway(
        providers=[
            StubProvider(
                "openai",
                ReasoningResult(False, "failed", "openai", "m1", "v1", None, None, None, 10, "timeout", True),
            ),
            StubProvider(
                "anthropic",
                ReasoningResult(False, "failed", "anthropic", "m2", "v1", None, None, None, 20, "rate limit", True),
            ),
        ]
    )

    result = await gateway.run(_request())
    assert result.success is False
    assert result.status == "pending"


async def test_gateway_escalates_when_first_provider_returns_odd_signal_mapping():
    gateway = ThesisReasoningGateway(
        providers=[
            StubProvider(
                "openai",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="openai",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "medium",
                        "decomposition_confidence": 0.9,
                        "claims": [
                            {
                                "claim_text": "Margins should expand.",
                                "claim_type": "margins",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "entity_name": "Apple Inc",
                                        "entity_ticker": "AAPL",
                                        "entity_type": "held_company",
                                        "signals": [
                                            {
                                                "signal_type": "macro_series_change",
                                                "signal_label": "Macro series",
                                                "confidence": 0.9,
                                                "confirmation_required": False,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            ),
            StubProvider(
                "anthropic",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="anthropic",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "medium",
                        "decomposition_confidence": 0.8,
                        "claims": [
                            {
                                "claim_text": "Margins should expand.",
                                "claim_type": "margins",
                                "confidence": 0.8,
                                "entities": [
                                    {
                                        "entity_name": "Apple Inc",
                                        "entity_ticker": "AAPL",
                                        "entity_type": "held_company",
                                        "signals": [
                                            {
                                                "signal_type": "guidance_change",
                                                "signal_label": "Guidance commentary",
                                                "confidence": 0.8,
                                                "confirmation_required": False,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            ),
        ]
    )

    result = await gateway.run(_request("Margins should expand as the product mix improves."))
    assert result.success is True
    assert result.provider == "anthropic"


async def test_gateway_allows_earnings_growth_for_demand_claims():
    gateway = ThesisReasoningGateway(
        providers=[
            StubProvider(
                "openai",
                ReasoningResult(
                    success=True,
                    status="success",
                    provider="openai",
                    model="test-model",
                    prompt_version="v1",
                    normalized_output=None,
                    raw_output={
                        "reason_type": "business_performance",
                        "monitorability": "high",
                        "decomposition_confidence": 0.9,
                        "claims": [
                            {
                                "claim_text": "AI demand should keep driving datacenter growth.",
                                "claim_type": "demand",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "entity_name": "NVIDIA",
                                        "entity_ticker": "NVDA",
                                        "entity_type": "held_company",
                                        "signals": [
                                            {
                                                "signal_type": "earnings_growth",
                                                "signal_label": "Earnings growth",
                                                "confidence": 0.9,
                                                "confirmation_required": False,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            )
        ]
    )

    result = await gateway.run(_request("AI demand continues to drive strong datacenter GPU sales growth."))
    assert result.success is True
    assert result.provider == "openai"
