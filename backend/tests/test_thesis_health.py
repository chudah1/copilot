from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_thesis_response_omits_legacy_health_fields(client, auth_headers):
    with patch(
        "app.services.ai_thesis.generate_draft_theses_for_user",
        new_callable=AsyncMock,
    ):
        holding_resp = await client.post(
            "/api/portfolio/holdings",
            json={
                "ticker": "MSFT",
                "name": "Microsoft",
                "quantity": 5,
                "average_cost_basis": 300.0,
            },
            headers=auth_headers,
        )
    holding_id = holding_resp.json()["id"]

    resp = await client.post(
        "/api/theses",
        json={
            "holding_id": holding_id,
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Cloud dominance via Azure.",
            "what_would_change_my_mind": "Revenue decline or margin compression.",
            "confidence": "high",
            "source": "user",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "health_score" not in data
    assert "health_label" not in data
