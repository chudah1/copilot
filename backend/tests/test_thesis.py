from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_thesis import ThesisAssistOutput
from app.services.reasoning.types import ReasoningResult


@pytest.fixture
async def holding(client, auth_headers):
    with patch("app.services.ai_thesis.generate_draft_theses_for_user", new_callable=AsyncMock):
        response = await client.post(
            "/api/portfolio/holdings",
            json={"ticker": "AAPL", "name": "Apple Inc", "quantity": 10, "average_cost_basis": 150.50},
            headers=auth_headers,
        )
    return response.json()


class MockGateway:
    def __init__(self, result: ReasoningResult):
        self._result = result
        self.run = AsyncMock(return_value=result)


async def test_create_thesis(client, auth_headers, holding):
    response = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "I own Apple for ecosystem strength.",
            "must_remain_true": "Services growth stays healthy.",
            "what_would_change_my_mind": "Margin compression without recovery.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["why_own_it"] == "I own Apple for ecosystem strength."
    assert data["status"] == "active"
    assert data["source"] == "user"


async def test_assist_thesis_does_not_persist(client, auth_headers, holding):
    mock_output = ThesisAssistOutput(
        why_own_it="Apple's ecosystem keeps users locked in and supports durable cash generation.",
        must_remain_true="Services growth and retention stay strong.",
        what_would_change_my_mind="A sustained ecosystem weakening or services slowdown.",
        ai_summary="Apple is held for ecosystem durability.",
        interpretation={
            "labels": ["quality"],
            "monitorability": "high",
            "watch_hints": [{"kind": "price_move_pct", "threshold": 10.0, "rationale": "Review sharp moves."}],
            "ambiguity_note": "",
        },
    )
    with patch("app.routes.thesis.assist_thesis", new_callable=AsyncMock, return_value=mock_output):
        response = await client.post(
            "/api/theses/assist",
            json={"holding_id": holding["id"], "draft_text": "I like the ecosystem"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["why_own_it"].startswith("Apple")
    assert data["must_remain_true"] == "Services growth and retention stay strong."
    assert data["ai_summary"] == "Apple is held for ecosystem durability."

    theses_response = await client.get(f"/api/theses/holding/{holding['id']}", headers=auth_headers)
    assert theses_response.status_code == 200
    assert theses_response.json() == []


async def test_assist_thesis_returns_502_when_live_assist_fails(client, auth_headers, holding):
    with patch("app.routes.thesis.assist_thesis", new_callable=AsyncMock, return_value=None):
        response = await client.post(
            "/api/theses/assist",
            json={"holding_id": holding["id"], "draft_text": "I like the ecosystem"},
            headers=auth_headers,
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to assist thesis draft"


async def test_debug_decompose_returns_provider_and_gateway_results(client, auth_headers):
    debug_payload = {
        "providers": [
            {
                "provider": "openai",
                "model": "gpt-4.1-mini",
                "success": True,
                "status": "success",
                "latency_ms": 1200,
                "failure_reason": None,
                "raw_output": {"reason_type": "business_performance"},
                "normalized_output": {
                    "reason_type": "business_performance",
                    "monitorability": "high",
                    "decomposition_confidence": 0.9,
                    "claims": [],
                },
                "valid": True,
                "validation_error": None,
            }
        ],
        "gateway_result": {
            "success": True,
            "status": "success",
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "confidence": 0.9,
            "latency_ms": 1200,
            "failure_reason": None,
            "normalized_output": {
                "reason_type": "business_performance",
                "monitorability": "high",
                "decomposition_confidence": 0.9,
                "claims": [],
            },
        },
    }

    with patch(
        "app.routes.thesis.debug_compare_decomposition_providers",
        new_callable=AsyncMock,
        return_value=debug_payload,
    ):
        response = await client.post(
            "/api/theses/debug/decompose",
            json={
                "ticker": "AAPL",
                "name": "Apple Inc",
                "why_own_it": "I own Apple because services revenue is resilient.",
                "must_remain_true": "Services growth stays healthy.",
                "what_would_change_my_mind": "Margin deterioration.",
            },
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["providers"]) == 1
    assert data["providers"][0]["provider"] == "openai"
    assert data["providers"][0]["valid"] is True
    assert data["gateway_result"]["provider"] == "openai"
    assert data["gateway_result"]["success"] is True


async def test_update_thesis(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "draft",
            "thesis_kind": "company",
            "why_own_it": "Initial draft.",
            "what_would_change_my_mind": "Weak demand and lower margins.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    response = await client.put(
        f"/api/theses/{thesis_id}",
        json={
            "why_own_it": "Updated thesis.",
            "must_remain_true": "Demand remains strong.",
            "what_would_change_my_mind": "Weak demand and lower margins.",
            "confidence": "high",
            "status": "active",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["confidence"] == "high"
    assert response.json()["must_remain_true"] == "Demand remains strong."


async def test_list_current_theses_returns_latest_current_per_holding(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "draft",
            "thesis_kind": "company",
            "why_own_it": "Initial draft.",
            "what_would_change_my_mind": "Material slowdown in services revenue.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    await client.put(
        f"/api/theses/{thesis_id}",
        json={"status": "needs_review"},
        headers=auth_headers,
    )

    response = await client.get("/api/theses/current", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["holding_id"] == holding["id"]
    assert data[0]["status"] == "needs_review"


async def test_invalidate_thesis(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Hold for platform strength.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    response = await client.post(
        f"/api/theses/{thesis_id}/invalidate",
        json={"reason": "The original thesis broke."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "invalidated"
    assert response.json()["invalidation_reason"] == "The original thesis broke."


async def test_reaffirm_thesis_resets_status_to_active(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "needs_review",
            "thesis_kind": "company",
            "why_own_it": "Hold for platform strength.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    response = await client.post(f"/api/theses/{thesis_id}/reaffirm", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "active"


async def test_decompose_thesis_persists_nested_records(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "AI demand should support Apple services and device upgrades.",
            "must_remain_true": "Demand remains healthy.",
            "what_would_change_my_mind": "Demand slows materially.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.91,
            "claims": [
                {
                    "claim_text": "Demand remains healthy.",
                    "claim_type": "demand",
                    "confidence": 0.88,
                    "entities": [
                        {
                            "entity_name": "Apple Inc",
                            "entity_ticker": "AAPL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Apple execution matters directly.",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "Apple revenue growth",
                                    "signal_config_json": {"operator": ">=", "threshold": 0.0},
                                    "rationale": "Revenue growth should stay positive.",
                                    "confidence": 0.92,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.91,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    envelope = response.json()
    assert envelope["status"] == "draft"
    data = envelope["decomposition"]
    assert data["version"] == 1
    assert data["reason_type"] == "business_performance"
    assert len(data["claims"]) == 1
    assert data["claims"][0]["claim_type"] == "demand"
    assert data["claims"][0]["entities"][0]["entity_ticker"] == "AAPL"
    assert data["claims"][0]["entities"][0]["signals"][0]["signal_type"] == "revenue_growth"
    assert data["claims"][0]["entities"][0]["signals"][0]["active"] is True


async def test_decomposition_version_increments_on_rerun(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "I own Apple for ecosystem strength.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "medium",
            "decomposition_confidence": 0.7,
            "claims": [
                {
                    "claim_text": "Ecosystem strength remains durable.",
                    "claim_type": "other",
                    "confidence": 0.7,
                    "entities": [],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.7,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        first = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)
        second = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["decomposition"]["version"] == 1
    assert second.json()["decomposition"]["version"] == 2


async def test_get_latest_decomposition_returns_nested_structure(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "I own Apple because services are resilient.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "medium",
            "decomposition_confidence": 0.65,
            "claims": [
                {
                    "claim_text": "Services remain resilient.",
                    "claim_type": "other",
                    "confidence": 0.65,
                    "entities": [],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.65,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    response = await client.get(f"/api/theses/{thesis_id}/decomposition", headers=auth_headers)
    assert response.status_code == 200
    envelope = response.json()
    assert envelope["status"] == "draft"
    data = envelope["decomposition"]
    assert data["thesis_id"] == thesis_id
    assert isinstance(data["claims"], list)
    if data["claims"]:
        assert "entities" in data["claims"][0]


async def test_get_latest_decomposition_returns_confirmed_decomposition(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple benefits from stronger supply chain demand.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "macro_theme",
            "monitorability": "medium",
            "decomposition_confidence": 0.7,
            "claims": [
                {
                    "claim_text": "Upstream demand remains strong.",
                    "claim_type": "demand",
                    "confidence": 0.7,
                    "entities": [
                        {
                            "entity_name": "TSMC",
                            "entity_ticker": "TSM",
                            "entity_type": "supplier",
                            "relation_type": "validated_by",
                            "rationale": "TSMC is a proxy for supply chain demand.",
                            "confidence": 0.7,
                            "confirmation_required": True,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "TSMC demand commentary",
                                    "signal_config_json": {},
                                    "rationale": "Proxy commentary matters.",
                                    "confidence": 0.7,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.7,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        decompose_response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    decomposition = decompose_response.json()["decomposition"]
    entity = decomposition["claims"][0]["entities"][0]
    signal = entity["signals"][0]

    confirm_response = await client.post(
        f"/api/theses/{thesis_id}/decomposition/confirm",
        json={
            "decomposition_id": decomposition["id"],
            "entities": [{"id": entity["id"], "user_confirmed": True}],
            "signals": [{"id": signal["id"], "user_confirmed": True, "active": True}],
        },
        headers=auth_headers,
    )
    assert confirm_response.status_code == 200

    latest_response = await client.get(f"/api/theses/{thesis_id}/decomposition", headers=auth_headers)
    assert latest_response.status_code == 200
    envelope = latest_response.json()
    assert envelope["status"] == "confirmed"
    assert envelope["decomposition"] is not None
    assert envelope["decomposition"]["status"] == "confirmed"
    assert envelope["decomposition"]["claims"][0]["entities"][0]["signals"][0]["active"] is True


async def test_get_latest_decomposition_returns_404_when_missing(client, auth_headers):
    response = await client.get("/api/theses/00000000-0000-0000-0000-000000000000/decomposition", headers=auth_headers)
    assert response.status_code == 404


async def test_decompose_failure_falls_back_to_monitorable_floor(client, auth_headers, holding):
    """Never-fail: an unusable gateway result no longer dead-ends the thesis.

    Instead of returning 'failed' with no decomposition, the system persists a
    monitorable baseline floor (an active coarse price-move signal) so the
    thesis is still watched.
    """
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "draft",
            "thesis_kind": "company",
            "why_own_it": "They make iPhones.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]

    gateway_result = ReasoningResult(
        success=False,
        status="pending",
        provider="gemini",
        model="gemini-test",
        prompt_version="v1",
        normalized_output=None,
        raw_output=None,
        confidence=None,
        latency_ms=500,
        failure_reason="All providers failed or returned unusable output.",
        retryable=True,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    envelope = response.json()
    assert envelope["status"] == "partially_confirmed"
    assert envelope["decomposition"] is not None
    assert "baseline monitoring" in (envelope["message"] or "")

    decomp = envelope["decomposition"]
    assert decomp["monitorability"] == "low"
    signals = [
        s
        for claim in decomp["claims"]
        for entity in claim["entities"]
        for s in entity["signals"]
    ]
    assert any(s["signal_type"] == "price_move" and s["active"] for s in signals)

    # The thesis is monitorable: interpretation is populated.
    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    assert thesis_response.json()["interpretation"] is not None

    decomposition_response = await client.get(f"/api/theses/{thesis_id}/decomposition", headers=auth_headers)
    assert decomposition_response.status_code == 200
    assert decomposition_response.json()["status"] == "partially_confirmed"


async def test_decompose_auto_activates_direct_high_confidence_signal_and_syncs_interpretation(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Revenue should keep growing.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.89,
            "claims": [
                {
                    "claim_text": "Revenue should keep growing.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": "Apple Inc",
                            "entity_ticker": "AAPL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Direct company execution matters.",
                            "confidence": 0.96,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "Apple revenue growth",
                                    "signal_config_json": {"operator": ">=", "threshold": 0.0},
                                    "rationale": "Revenue growth should stay positive.",
                                    "confidence": 0.91,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.89,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True

    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    interpretation = thesis_response.json()["interpretation"]
    assert interpretation is not None
    assert interpretation["monitorability"] == "high"
    assert interpretation["watch_hints"][0]["metric"] == "revenue_growth_yoy"


async def test_proxy_signal_remains_inactive_and_not_projected(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple benefits from stronger supply chain demand.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "macro_theme",
            "monitorability": "medium",
            "decomposition_confidence": 0.61,
            "claims": [
                {
                    "claim_text": "Upstream demand remains strong.",
                    "claim_type": "demand",
                    "confidence": 0.64,
                    "entities": [
                        {
                            "entity_name": "TSMC",
                            "entity_ticker": "TSM",
                            "entity_type": "supplier",
                            "relation_type": "validated_by",
                            "rationale": "TSMC is a proxy for supply chain demand.",
                            "confidence": 0.62,
                            "confirmation_required": True,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "TSMC demand commentary",
                                    "signal_config_json": {},
                                    "rationale": "Proxy commentary matters.",
                                    "confidence": 0.6,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.61,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is False
    assert signal["user_confirmed"] is None

    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    assert thesis_response.json()["interpretation"] is None


async def test_margin_proxy_signal_requires_review_and_does_not_auto_activate(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Gross margins should stay healthy.",
            "what_would_change_my_mind": "Gross margin compression would weaken the case.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "unit_economics",
            "monitorability": "high",
            "decomposition_confidence": 0.84,
            "claims": [
                {
                    "claim_text": "Gross margins stay healthy.",
                    "claim_type": "profitability",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "Apple Inc",
                            "entity_ticker": "AAPL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Company margin trend matters directly.",
                            "confidence": 0.93,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "earnings_growth",
                                    "signal_label": "Apple gross margin trend",
                                    "signal_config_json": {"metric": "gross_margin", "operator": ">="},
                                    "rationale": "Gross margin compression would weaken the case.",
                                    "confidence": 0.92,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.84,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is False
    assert signal["user_confirmed"] is None
    assert signal["confirmation_required"] is True
    assert signal["signal_config_json"]["proxy_review_required"] is True

    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    assert thesis_response.json()["interpretation"] is None


async def test_internal_kpi_proxy_requires_review_and_does_not_auto_activate(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Capacity should convert into signed customer demand.",
            "what_would_change_my_mind": "Contracted demand stops showing up.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="openai",
        model="gpt-5.5",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "medium",
            "decomposition_confidence": 0.82,
            "claims": [
                {
                    "claim_text": "Capacity expansion keeps converting into signed customer demand.",
                    "claim_type": "demand",
                    "confidence": 0.82,
                    "entities": [
                        {
                            "entity_name": "Apple Inc",
                            "entity_ticker": "AAPL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Buildout must become contracted demand.",
                            "confidence": 0.86,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "ORCL remaining performance obligations growth",
                                    "signal_config_json": {},
                                    "rationale": "RPO indicates contracted future revenue.",
                                    "confidence": 0.82,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "openai"},
        confidence=0.82,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is False
    assert signal["confirmation_required"] is True
    assert signal["signal_config_json"]["proxy_source_metric"] == "remaining_performance_obligations_growth"
    assert signal["signal_config_json"]["proxy_review_required"] is True


async def test_confirm_decomposition_activates_proxy_signal_and_updates_status(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Apple benefits from stronger supply chain demand.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "medium",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "macro_theme",
            "monitorability": "medium",
            "decomposition_confidence": 0.7,
            "claims": [
                {
                    "claim_text": "Upstream demand remains strong.",
                    "claim_type": "demand",
                    "confidence": 0.7,
                    "entities": [
                        {
                            "entity_name": "TSMC",
                            "entity_ticker": "TSM",
                            "entity_type": "supplier",
                            "relation_type": "validated_by",
                            "rationale": "TSMC is a proxy for supply chain demand.",
                            "confidence": 0.7,
                            "confirmation_required": True,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "TSMC demand commentary",
                                    "signal_config_json": {},
                                    "rationale": "Proxy commentary matters.",
                                    "confidence": 0.7,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.7,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        decompose_response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    decomposition = decompose_response.json()["decomposition"]
    entity = decomposition["claims"][0]["entities"][0]
    signal = entity["signals"][0]

    response = await client.post(
        f"/api/theses/{thesis_id}/decomposition/confirm",
        json={
            "decomposition_id": decomposition["id"],
            "entities": [{"id": entity["id"], "user_confirmed": True}],
            "signals": [{"id": signal["id"], "user_confirmed": True, "active": True}],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["status"] == "confirmed"
    confirmed_signal = envelope["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert confirmed_signal["user_confirmed"] is True
    assert confirmed_signal["active"] is True


async def test_decompose_auto_activates_strong_held_company_transcript_signal(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Blackwell deployment keeps strengthening demand.",
            "what_would_change_my_mind": "Deployment bottlenecks emerge.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.88,
            "claims": [
                {
                    "claim_text": "Blackwell deployment continues on plan.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": holding["name"],
                            "entity_ticker": holding["ticker"],
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Management commentary confirms rollout health.",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "NVDA Blackwell deployment",
                                    "signal_config_json": {"topic": "Blackwell deployment"},
                                    "rationale": "Transcript discussion should confirm rollout progress.",
                                    "confidence": 0.93,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.88,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True
    assert signal["signal_config_json"]["direction"] == "supports"
    assert signal["signal_config_json"]["watch_for"] == "Blackwell deployment"

    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    interpretation = thesis_response.json()["interpretation"]
    assert interpretation is not None
    assert interpretation["watch_hints"][0]["kind"] == "news_watch"
    assert interpretation["watch_hints"][0]["watch_for"] == "Blackwell deployment"
    assert interpretation["watch_hints"][0]["direction"] == "supports"


async def test_decompose_auto_activates_held_company_news_topic_without_entity_ticker(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Demand commentary should keep validating the case.",
            "what_would_change_my_mind": "Demand weakens materially.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.88,
            "claims": [
                {
                    "claim_text": "Demand commentary keeps validating the case.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": holding["name"],
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Direct company commentary matters.",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "Apple services demand news",
                                    "signal_config_json": {"topic": "services demand"},
                                    "rationale": "News should confirm demand stays healthy.",
                                    "confidence": 0.86,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.88,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True
    assert signal["signal_config_json"]["watch_for"] == "services demand"


async def test_decompose_auto_activates_explicit_high_confidence_threat_watch(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Regulatory access must stay open.",
            "what_would_change_my_mind": "A direct restriction would break the case.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "regulatory",
            "monitorability": "high",
            "decomposition_confidence": 0.87,
            "claims": [
                {
                    "claim_text": "The FDA does not restrict access.",
                    "claim_type": "risk",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": "FDA",
                            "entity_type": "other",
                            "relation_type": "threatened_by",
                            "rationale": "Regulatory restriction would directly break the case.",
                            "confidence": 0.9,
                            "confirmation_required": True,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "FDA restriction news",
                                    "signal_config_json": {"topic": "FDA restriction"},
                                    "rationale": "Restriction news would threaten the case.",
                                    "confidence": 0.86,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.87,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True
    assert signal["signal_config_json"]["direction"] == "threatens"


async def test_decompose_auto_activates_explicit_high_confidence_transcript_watch(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Management needs a credible replacement plan.",
            "what_would_change_my_mind": "No credible replacement plan emerges.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.86,
            "claims": [
                {
                    "claim_text": "Management presents a credible replacement path.",
                    "claim_type": "growth",
                    "confidence": 0.88,
                    "entities": [
                        {
                            "entity_name": holding["name"],
                            "entity_ticker": holding["ticker"],
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Management commentary should confirm contingency planning.",
                            "confidence": 0.9,
                            "confirmation_required": True,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "Management replacement path discussion",
                                    "signal_config_json": {"topic": "replacement path discussion"},
                                    "rationale": "Transcript discussion should confirm a credible replacement path.",
                                    "confidence": 0.82,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.86,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True
    assert signal["signal_config_json"]["watch_for"] == "replacement path discussion"


async def test_decompose_adds_active_integration_companion_watches(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "The acquisition should add new revenue without becoming overhead drag.",
            "what_would_change_my_mind": "The deal adds cost without clear new revenue traction.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.84,
            "claims": [
                {
                    "claim_text": "The acquisition adds a clear new revenue line without overhead drag.",
                    "claim_type": "growth",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "TargetCo",
                            "entity_ticker": "TGCO",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "The deal must add revenue rather than just overhead.",
                            "confidence": 0.84,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "TargetCo acquisition revenue contribution",
                                    "signal_config_json": {"operator": ">=", "threshold_pct": 0.0},
                                    "rationale": "Revenue contribution validates the acquisition case.",
                                    "confidence": 0.84,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "earnings_growth",
                                    "signal_label": "TargetCo acquisition cost impact",
                                    "signal_config_json": {"operator": ">=", "threshold_pct": 0.0},
                                    "rationale": "Cost impact should not turn into overhead drag.",
                                    "confidence": 0.84,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.84,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signals = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"]
    active_news_topics = [s for s in signals if s["signal_type"] == "news_topic" and s["active"]]
    assert {s["signal_label"] for s in active_news_topics} == {
        "TargetCo integration revenue traction",
        "TargetCo integration overhead drag",
    }


async def test_decompose_auto_activates_explicit_integration_topic_on_non_primary_entity(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "The acquisition should deepen monetization without integration drag.",
            "what_would_change_my_mind": "The acquisition fails to deepen monetization or turns into overhead drag.",
            "confidence": "high",
            "review_cadence_days": 21,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.84,
            "claims": [
                {
                    "claim_text": "The acquisition deepens monetization without becoming overhead drag.",
                    "claim_type": "growth",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "TargetCo",
                            "entity_ticker": "TGCO",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Integration should deepen subscription monetization.",
                            "confidence": 0.84,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "TargetCo integration monetization progress",
                                    "signal_config_json": {
                                        "topic": "TargetCo integration monetization progress",
                                        "watch_for": "TargetCo integration monetization progress",
                                        "direction": "supports",
                                    },
                                    "rationale": "Integration progress should show up as clearer monetization traction.",
                                    "confidence": 0.82,
                                    "confirmation_required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.84,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signal = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert signal["active"] is True
    assert signal["user_confirmed"] is True


async def test_decompose_adds_fallback_regulatory_watch_when_model_misses_it(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Services should keep compounding and the installed base should stay sticky.",
            "must_remain_true": "Services revenue keeps growing double digits.",
            "what_would_change_my_mind": "Regulatory pressure forces meaningful changes to App Store economics without a replacement monetization path.",
            "confidence": "high",
            "review_cadence_days": 21,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.9,
            "claims": [
                {
                    "claim_text": "Services revenue keeps compounding.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": holding["name"],
                            "entity_ticker": holding["ticker"],
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Services growth matters most.",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "AAPL Services revenue growth",
                                    "signal_config_json": {"operator": ">=", "threshold_pct": 10.0},
                                    "rationale": "Double-digit services growth is required.",
                                    "confidence": 0.95,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.9,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signals = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"]
    fallback_watch = next(s for s in signals if s["signal_type"] == "news_watch")
    assert fallback_watch["active"] is True
    assert fallback_watch["user_confirmed"] is True
    assert "App Store economics" in fallback_watch["signal_config_json"]["watch_for"]


async def test_decompose_adds_fallback_credit_and_usage_watches_when_model_misses_them(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Merchant adoption and repeat user growth should keep driving gross merchandise volume while the funding model stays available.",
            "must_remain_true": "Funding capacity remains available without ugly credit deterioration.",
            "what_would_change_my_mind": "Funding costs spike and management cannot offset them, delinquencies rise enough to show underwriting is breaking, or merchant growth stalls and repeat usage weakens.",
            "confidence": "high",
            "review_cadence_days": 21,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.9,
            "claims": [
                {
                    "claim_text": "Gross merchandise volume keeps compounding.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": holding["name"],
                            "entity_ticker": holding["ticker"],
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Volume growth matters most.",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "Gross merchandise volume growth",
                                    "signal_config_json": {"operator": ">=", "threshold_pct": 0.0},
                                    "rationale": "Volume growth validates demand.",
                                    "confidence": 0.95,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.9,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    signals = response.json()["decomposition"]["claims"][0]["entities"][0]["signals"]
    fallback_watches = [s for s in signals if s["signal_type"] == "news_watch" and s["active"]]
    watch_fors = {s["signal_config_json"]["watch_for"] for s in fallback_watches}
    assert "funding costs spike or funding capacity tightens and management cannot offset it" in watch_fors
    assert "delinquencies rise enough to show underwriting is breaking" in watch_fors
    assert "merchant growth stalls and repeat usage weakens materially" in watch_fors


async def test_confirm_decomposition_can_reject_active_signal_and_clear_interpretation(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Revenue should keep growing.",
            "what_would_change_my_mind": "Material deterioration in fundamentals.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    thesis_id = create.json()["id"]
    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="anthropic",
        model="claude-test",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "high",
            "decomposition_confidence": 0.89,
            "claims": [
                {
                    "claim_text": "Revenue should keep growing.",
                    "claim_type": "growth",
                    "confidence": 0.9,
                    "entities": [
                        {
                            "entity_name": "Apple Inc",
                            "entity_ticker": "AAPL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Direct company execution matters.",
                            "confidence": 0.96,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "Apple revenue growth",
                                    "signal_config_json": {"operator": ">=", "threshold": 0.0},
                                    "rationale": "Revenue growth should stay positive.",
                                    "confidence": 0.91,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        raw_output={"provider": "anthropic"},
        confidence=0.89,
        latency_ms=120,
        failure_reason=None,
    )
    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        decompose_response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    decomposition = decompose_response.json()["decomposition"]
    entity = decomposition["claims"][0]["entities"][0]
    signal = entity["signals"][0]

    response = await client.post(
        f"/api/theses/{thesis_id}/decomposition/confirm",
        json={
            "decomposition_id": decomposition["id"],
            "entities": [{"id": entity["id"], "user_confirmed": False}],
            "signals": [{"id": signal["id"], "user_confirmed": False, "active": False}],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    envelope = response.json()
    assert envelope["status"] == "rejected"
    rejected_signal = envelope["decomposition"]["claims"][0]["entities"][0]["signals"][0]
    assert rejected_signal["user_confirmed"] is False
    assert rejected_signal["active"] is False

    thesis_response = await client.get(f"/api/theses/{thesis_id}", headers=auth_headers)
    assert thesis_response.json()["interpretation"] is None


async def test_thesis_routes_require_auth(client, holding):
    response = await client.get(f"/api/theses/holding/{holding['id']}")
    assert response.status_code == 403
