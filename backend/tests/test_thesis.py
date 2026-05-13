from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_thesis import ThesisAssistOutput
from app.services.reasoning.types import ReasoningResult


@pytest.fixture
async def holding(client, auth_headers):
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
    assert data["ai_summary"] == "Apple is held for ecosystem durability."

    theses_response = await client.get(f"/api/theses/holding/{holding['id']}", headers=auth_headers)
    assert theses_response.status_code == 200
    assert theses_response.json() == []


async def test_update_thesis(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "draft",
            "thesis_kind": "company",
            "why_own_it": "Initial draft.",
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


async def test_get_latest_decomposition_returns_404_when_missing(client, auth_headers):
    response = await client.get("/api/theses/00000000-0000-0000-0000-000000000000/decomposition", headers=auth_headers)
    assert response.status_code == 404


async def test_decompose_descriptive_thesis_yields_no_auto_active_signals(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "draft",
            "thesis_kind": "company",
            "why_own_it": "They make iPhones.",
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

    assert response.status_code == 202
    envelope = response.json()
    assert envelope["status"] == "pending"
    assert envelope["decomposition"] is None

    decomposition_response = await client.get(f"/api/theses/{thesis_id}/decomposition", headers=auth_headers)
    assert decomposition_response.status_code == 200
    assert decomposition_response.json()["status"] == "pending"


async def test_decompose_auto_activates_direct_high_confidence_signal_and_syncs_interpretation(client, auth_headers, holding):
    create = await client.post(
        "/api/theses",
        json={
            "holding_id": holding["id"],
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Revenue should keep growing.",
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


async def test_thesis_routes_require_auth(client, holding):
    response = await client.get(f"/api/theses/holding/{holding['id']}")
    assert response.status_code == 403
