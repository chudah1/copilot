from unittest.mock import AsyncMock, patch

from app.services.reasoning.types import ReasoningResult


class MockGateway:
    def __init__(self, result: ReasoningResult):
        self.run = AsyncMock(return_value=result)


async def _create_holding(client, auth_headers, *, ticker: str, name: str):
    with patch("app.services.ai_thesis.generate_draft_theses_for_user", new_callable=AsyncMock):
        response = await client.post(
            "/api/portfolio/holdings",
            json={"ticker": ticker, "name": name, "quantity": 10, "average_cost_basis": 100.0},
            headers=auth_headers,
        )
    assert response.status_code == 201
    return response.json()


async def _create_thesis(client, auth_headers, holding_id: str, *, why: str, must: str, change: str):
    response = await client.post(
        "/api/theses",
        json={
            "holding_id": holding_id,
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": why,
            "must_remain_true": must,
            "what_would_change_my_mind": change,
            "confidence": "high",
            "review_cadence_days": 14,
            "source": "user",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _all_signals(response_json: dict) -> list[dict]:
    claims = response_json["decomposition"]["claims"]
    return [
        signal
        for claim in claims
        for entity in claim["entities"]
        for signal in entity["signals"]
    ]


async def test_orcl_benchmark_keeps_renewals_and_payback_branches(client, auth_headers):
    holding = await _create_holding(client, auth_headers, ticker="ORCL", name="Oracle Corporation")
    thesis_id = await _create_thesis(
        client,
        auth_headers,
        holding["id"],
        why="OCI demand and enterprise migrations are driving a real second act.",
        must="Capacity should convert into signed customer demand and large contracts should keep renewing.",
        change="I would reconsider if renewals slip or capex buildout crushes margins without payback.",
    )

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
                    "claim_text": "ORCL OCI revenue growth remains strong as enterprises migrate workloads",
                    "claim_type": "growth",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "Oracle Corporation",
                            "entity_ticker": "ORCL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "OCI growth is central thesis outcome",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "ORCL OCI revenue growth",
                                    "signal_config_json": {},
                                    "rationale": "Tracks cloud infrastructure momentum",
                                    "confidence": 0.9,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "guidance_change",
                                    "signal_label": "ORCL cloud revenue guidance",
                                    "signal_config_json": {},
                                    "rationale": "Guidance shows expected durability",
                                    "confidence": 0.85,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "ORCL capacity expansion keeps converting into signed customer demand",
                    "claim_type": "demand",
                    "confidence": 0.82,
                    "entities": [
                        {
                            "entity_name": "Oracle Corporation",
                            "entity_ticker": "ORCL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Buildout must become contracted demand",
                            "confidence": 0.9,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "ORCL remaining performance obligations growth",
                                    "signal_config_json": {},
                                    "rationale": "RPO indicates contracted future revenue",
                                    "confidence": 0.82,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "ORCL capacity signed demand commentary",
                                    "signal_config_json": {},
                                    "rationale": "Management links capacity to bookings",
                                    "confidence": 0.78,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "ORCL large customer relationships renew and expand rather than slip",
                    "claim_type": "demand",
                    "confidence": 0.8,
                    "entities": [
                        {
                            "entity_name": "Oracle Corporation",
                            "entity_ticker": "ORCL",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Renewals sustain growth",
                            "confidence": 0.9,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "ORCL large contract renewals",
                                    "signal_config_json": {},
                                    "rationale": "Renewal losses would weaken thesis",
                                    "confidence": 0.78,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "ORCL capex and capacity buildout do not crush margins without payback",
                    "claim_type": "margins",
                    "confidence": 0.78,
                    "entities": [
                        {
                            "entity_name": "Oracle Corporation",
                            "entity_ticker": "ORCL",
                            "entity_type": "held_company",
                            "relation_type": "threatened_by",
                            "rationale": "Margin pressure without payback breaks thesis",
                            "confidence": 0.9,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "earnings_growth",
                                    "signal_label": "ORCL operating margin trend",
                                    "signal_config_json": {},
                                    "rationale": "Shows margin impact from buildout",
                                    "confidence": 0.88,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "ORCL capex payback commentary",
                                    "signal_config_json": {},
                                    "rationale": "Payback visibility offsets capex risk",
                                    "confidence": 0.76,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
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
    signals = _all_signals(response.json())
    labels = {signal["signal_label"] for signal in signals}
    assert {
        "ORCL OCI revenue growth",
        "ORCL cloud revenue guidance",
        "ORCL remaining performance obligations growth",
        "ORCL large contract renewals",
        "ORCL capex payback commentary",
    }.issubset(labels)
    rpo_signal = next(signal for signal in signals if signal["signal_label"] == "ORCL remaining performance obligations growth")
    assert rpo_signal["signal_config_json"]["proxy_source_metric"] == "remaining_performance_obligations_growth"
    assert rpo_signal["signal_config_json"]["proxy_review_required"] is True
    assert rpo_signal["active"] is False


async def test_afrm_benchmark_keeps_funding_and_underwriting_branches(client, auth_headers):
    holding = await _create_holding(client, auth_headers, ticker="AFRM", name="Affirm Holdings, Inc.")
    thesis_id = await _create_thesis(
        client,
        auth_headers,
        holding["id"],
        why="Merchant adoption and repeat usage should keep scaling the BNPL network.",
        must="Funding must remain available and underwriting must stay disciplined.",
        change="I would reconsider if funding tightens, delinquencies rise, or repeat usage weakens.",
    )

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
                    "claim_text": "AFRM merchant additions continue growing rather than stalling",
                    "claim_type": "growth",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "Affirm Holdings, Inc.",
                            "entity_ticker": "AFRM",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Merchant adoption is central to scale",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "AFRM gross merchandise volume growth",
                                    "signal_config_json": {},
                                    "rationale": "GMV reflects merchant network usage",
                                    "confidence": 0.82,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "AFRM funding capacity remains available without a material cost spike",
                    "claim_type": "cash_flow",
                    "confidence": 0.82,
                    "entities": [
                        {
                            "entity_name": "Affirm Holdings, Inc.",
                            "entity_ticker": "AFRM",
                            "entity_type": "held_company",
                            "relation_type": "depends_on",
                            "rationale": "BNPL growth requires accessible financing",
                            "confidence": 0.93,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "AFRM funding capacity availability",
                                    "signal_config_json": {},
                                    "rationale": "Capacity commentary indicates liquidity resilience",
                                    "confidence": 0.78,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "AFRM funding cost trend",
                                    "signal_config_json": {},
                                    "rationale": "Cost spikes would pressure economics",
                                    "confidence": 0.78,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "AFRM delinquencies stay controlled and do not show underwriting deterioration",
                    "claim_type": "cash_flow",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "Affirm Holdings, Inc.",
                            "entity_ticker": "AFRM",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Credit quality underpins disciplined scaling",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "AFRM delinquency rate trend",
                                    "signal_config_json": {},
                                    "rationale": "Rising delinquencies signal underwriting stress",
                                    "confidence": 0.8,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "AFRM operating margin improves as revenue and GMV scale",
                    "claim_type": "margins",
                    "confidence": 0.8,
                    "entities": [
                        {
                            "entity_name": "Affirm Holdings, Inc.",
                            "entity_ticker": "AFRM",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Operating leverage is a key upside driver",
                            "confidence": 0.94,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "earnings_growth",
                                    "signal_label": "AFRM operating margin improvement",
                                    "signal_config_json": {},
                                    "rationale": "Margin expansion confirms operating leverage",
                                    "confidence": 0.82,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
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
    labels = {signal["signal_label"] for signal in _all_signals(response.json())}
    assert {
        "AFRM gross merchandise volume growth",
        "AFRM funding capacity availability",
        "AFRM funding cost trend",
        "AFRM delinquency rate trend",
        "AFRM operating margin improvement",
    }.issubset(labels)


async def test_now_benchmark_keeps_renewal_expansion_and_ai_branches(client, auth_headers):
    holding = await _create_holding(client, auth_headers, ticker="NOW", name="ServiceNow, Inc.")
    thesis_id = await _create_thesis(
        client,
        auth_headers,
        holding["id"],
        why="Workflow standardization and AI-assisted automation should deepen enterprise adoption.",
        must="Renewals, expansion, AI adoption, and margin discipline all need to hold.",
        change="I would reconsider if renewals slip, expansion weakens, AI fails to enlarge deals, or margins deteriorate.",
    )

    gateway_result = ReasoningResult(
        success=True,
        status="success",
        provider="openai",
        model="gpt-5.5",
        prompt_version="v1",
        normalized_output={
            "reason_type": "business_performance",
            "monitorability": "medium",
            "decomposition_confidence": 0.86,
            "claims": [
                {
                    "claim_text": "NOW subscription revenue keeps growing durably through enterprise workflow standardization",
                    "claim_type": "growth",
                    "confidence": 0.88,
                    "entities": [
                        {
                            "entity_name": "ServiceNow, Inc.",
                            "entity_ticker": "NOW",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Subscription growth is central",
                            "confidence": 0.95,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "NOW subscription revenue growth",
                                    "signal_config_json": {},
                                    "rationale": "Tracks durability of subscription growth",
                                    "confidence": 0.9,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "guidance_change",
                                    "signal_label": "NOW subscription revenue guidance",
                                    "signal_config_json": {},
                                    "rationale": "Forward outlook validates growth durability",
                                    "confidence": 0.85,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "NOW large customer renewals do not start slipping",
                    "claim_type": "demand",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "ServiceNow, Inc.",
                            "entity_ticker": "NOW",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Renewal strength supports platform value",
                            "confidence": 0.92,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "NOW large customer renewal trends",
                                    "signal_config_json": {},
                                    "rationale": "Management commentary reveals renewal slippage",
                                    "confidence": 0.82,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "NOW net expansion remains healthy and does not weaken materially",
                    "claim_type": "growth",
                    "confidence": 0.86,
                    "entities": [
                        {
                            "entity_name": "ServiceNow, Inc.",
                            "entity_ticker": "NOW",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Expansion proves multi-product adoption continues",
                            "confidence": 0.94,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "revenue_growth",
                                    "signal_label": "NOW net expansion rate trend",
                                    "signal_config_json": {},
                                    "rationale": "Direct measure of account expansion",
                                    "confidence": 0.88,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "NOW AI workflow products deepen adoption and translate into larger deals",
                    "claim_type": "demand",
                    "confidence": 0.84,
                    "entities": [
                        {
                            "entity_name": "ServiceNow, Inc.",
                            "entity_ticker": "NOW",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "AI adoption must drive deal expansion",
                            "confidence": 0.9,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "transcript_topic",
                                    "signal_label": "NOW AI workflow adoption",
                                    "signal_config_json": {},
                                    "rationale": "Adoption commentary validates AI product traction",
                                    "confidence": 0.84,
                                    "confirmation_required": False,
                                },
                                {
                                    "signal_type": "news_topic",
                                    "signal_label": "ServiceNow AI larger deals",
                                    "signal_config_json": {},
                                    "rationale": "Deal announcements show AI monetization",
                                    "confidence": 0.76,
                                    "confirmation_required": False,
                                },
                            ],
                        }
                    ],
                },
                {
                    "claim_text": "NOW operating margin discipline holds as the platform scales",
                    "claim_type": "margins",
                    "confidence": 0.84,
                    "entities": [
                        {
                            "entity_name": "ServiceNow, Inc.",
                            "entity_ticker": "NOW",
                            "entity_type": "held_company",
                            "relation_type": "validated_by",
                            "rationale": "Margin discipline protects profitable growth thesis",
                            "confidence": 0.92,
                            "confirmation_required": False,
                            "signals": [
                                {
                                    "signal_type": "earnings_growth",
                                    "signal_label": "NOW operating margin trend",
                                    "signal_config_json": {},
                                    "rationale": "Measures margin discipline at scale",
                                    "confidence": 0.88,
                                    "confirmation_required": False,
                                }
                            ],
                        }
                    ],
                },
            ],
        },
        raw_output={"provider": "openai"},
        confidence=0.86,
        latency_ms=120,
        failure_reason=None,
    )

    with patch("app.services.decomposition.get_reasoning_gateway", return_value=MockGateway(gateway_result)):
        response = await client.post(f"/api/theses/{thesis_id}/decompose", headers=auth_headers)

    assert response.status_code == 201
    labels = {signal["signal_label"] for signal in _all_signals(response.json())}
    assert {
        "NOW subscription revenue growth",
        "NOW large customer renewal trends",
        "NOW net expansion rate trend",
        "NOW AI workflow adoption",
        "ServiceNow AI larger deals",
        "NOW operating margin trend",
    }.issubset(labels)
