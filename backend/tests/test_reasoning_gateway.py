from app.services.reasoning.gateway import ThesisReasoningGateway
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.validators import output_needs_escalation


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
                        "claims": [{
                            "claim_text": "Revenue remains healthy.",
                            "source_field": "must_remain_true",
                            "claim_type": "growth",
                            "confidence": 0.8,
                            "entities": [],
                        }],
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
    assert result.normalized_output["claims"][0]["source_field"] == "must_remain_true"


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


async def test_gateway_salvages_valid_signals_when_one_mapping_is_invalid():
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
                                "claim_text": "Data center demand remains strong.",
                                "claim_type": "growth",
                                "confidence": 0.9,
                                "entities": [
                                    {
                                        "entity_name": "NVIDIA",
                                        "entity_ticker": "NVDA",
                                        "entity_type": "held_company",
                                        "signals": [
                                            {
                                                "signal_type": "revenue_growth",
                                                "signal_label": "Data center revenue growth",
                                                "confidence": 0.9,
                                                "confirmation_required": False,
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "claim_text": "Hyperscaler capex remains strong.",
                                "claim_type": "demand",
                                "confidence": 0.85,
                                "entities": [
                                    {
                                        "entity_name": "Hyperscalers",
                                        "entity_ticker": None,
                                        "entity_type": "customer",
                                        "signals": [
                                            {
                                                "signal_type": "macro_series_change",
                                                "signal_label": "Hyperscaler capex",
                                                "confidence": 0.85,
                                                "confirmation_required": False,
                                            }
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                    confidence=None,
                    latency_ms=50,
                    failure_reason=None,
                ),
            )
        ]
    )

    result = await gateway.run(_request("AI demand and capex should keep driving NVDA data center growth."))
    assert result.success is True
    assert result.provider == "openai"
    assert result.normalized_output is not None
    assert len(result.normalized_output["claims"]) == 1
    assert result.normalized_output["claims"][0]["entities"][0]["signals"][0]["signal_type"] == "revenue_growth"


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


def _proxy_heavy_output(confidence: float, *, all_signals_require_confirmation: bool, include_unflagged_signal: bool = False) -> dict:
    signal = {
        "signal_type": "news_topic",
        "signal_label": "competitor product launch",
        "confirmation_required": all_signals_require_confirmation,
    }
    extra_signals = []
    if include_unflagged_signal:
        extra_signals.append({
            "signal_type": "news_topic",
            "signal_label": "second signal without flag",
        })
    return {
        "reason_type": "mixed",
        "monitorability": "low",
        "decomposition_confidence": confidence,
        "claims": [
            {
                "claim_text": "Competitor erodes market share.",
                "claim_type": "growth",
                "entities": [
                    {
                        "entity_type": "competitor",
                        "signals": [signal] + extra_signals,
                    }
                ],
            }
        ],
    }


def test_proxy_gate_skipped_when_every_signal_self_flagged_for_confirmation():
    """Proxy-heavy output with confidence below 0.65 normally escalates, but if
    the LLM has already marked every signal `confirmation_required: true` the
    gate is double-counting humility — surface the claims for user confirmation
    instead of dropping them to baseline floor."""
    output = _proxy_heavy_output(0.6, all_signals_require_confirmation=True)
    escalate, reason = output_needs_escalation(output, original_text="some messy diary thesis")
    assert escalate is False, f"Should not escalate when self-flagged; reason={reason}"


def test_proxy_gate_still_fires_when_any_signal_not_self_flagged():
    """If the LLM mixed flagged and unflagged signals, treat it as
    insufficiently humble — gate still fires."""
    output = _proxy_heavy_output(0.6, all_signals_require_confirmation=True, include_unflagged_signal=True)
    escalate, reason = output_needs_escalation(output, original_text="some messy diary thesis")
    assert escalate is True
    assert reason == "Proxy-heavy decomposition requires higher confidence"


def test_proxy_gate_still_fires_when_signal_lacks_confirmation_field_entirely():
    """Older outputs without the confirmation_required field must not silently
    bypass the gate."""
    output = _proxy_heavy_output(0.6, all_signals_require_confirmation=False)
    escalate, reason = output_needs_escalation(output, original_text="some messy diary thesis")
    assert escalate is True
    assert reason == "Proxy-heavy decomposition requires higher confidence"


def test_low_confidence_in_soft_band_passes_when_every_signal_self_flagged():
    """Qualitative-only inputs produce honest low-confidence output (e.g. 0.5).
    The confidence-too-low gate used to discard those to the baseline floor;
    self-flagged signals absorb the residual uncertainty via UI confirmation,
    so the soft band (0.4 - 0.55) is now passable."""
    output = _proxy_heavy_output(0.5, all_signals_require_confirmation=True)
    escalate, reason = output_needs_escalation(output, original_text="qualitative thesis text")
    assert escalate is False, f"Soft-band confidence with self-flagged signals should pass; reason={reason}"


def test_low_confidence_in_soft_band_fails_when_not_self_flagged():
    """Without self-flagged signals there's no UI confirmation backstop, so
    the soft band still escalates."""
    output = _proxy_heavy_output(0.5, all_signals_require_confirmation=False)
    escalate, reason = output_needs_escalation(output, original_text="qualitative thesis text")
    assert escalate is True
    assert reason == "Decomposition confidence too low"


def test_low_confidence_below_hard_floor_always_escalates():
    """Confidence below the hard 0.4 floor escalates even when self-flagged —
    UI confirmation can't compensate for output that unreliable."""
    output = _proxy_heavy_output(0.35, all_signals_require_confirmation=True)
    escalate, reason = output_needs_escalation(output, original_text="qualitative thesis text")
    assert escalate is True
    assert reason == "Decomposition confidence too low"
