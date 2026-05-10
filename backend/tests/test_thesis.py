import uuid
from unittest.mock import patch, AsyncMock
from app.services.ai_thesis import ThesisOutput


# Helper fixture to create a holding
import pytest

@pytest.fixture
async def holding(client, auth_headers):
    response = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "AAPL", "name": "Apple Inc", "quantity": 10, "average_cost_basis": 150.50},
        headers=auth_headers,
    )
    return response.json()


async def test_generate_thesis(client, auth_headers, holding):
    mock_output = ThesisOutput(
        bull_case="Apple dominates premium smartphones.",
        key_metrics=[{"metric": "revenue_growth", "operator": ">=", "threshold": 10, "rationale": "Growth driver"}],
        risk_factors="Regulatory risk on App Store.",
        suggested_conviction="high",
    )
    with patch("app.routes.thesis.generate_thesis", new_callable=AsyncMock, return_value=mock_output):
        response = await client.post(
            "/api/theses/generate",
            json={"holding_id": holding["id"]},
            headers=auth_headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["bull_case"] == "Apple dominates premium smartphones."
    assert data["status"] == "draft"
    assert data["ai_generated"] is True


async def test_update_thesis_status_to_active(client, auth_headers, holding):
    mock_output = ThesisOutput(
        bull_case="Test case.",
        key_metrics=[{"metric": "pe_ratio", "operator": "<=", "threshold": 30, "rationale": "Valuation"}],
        risk_factors="Test risk.",
        suggested_conviction="medium",
    )
    with patch("app.routes.thesis.generate_thesis", new_callable=AsyncMock, return_value=mock_output):
        gen_response = await client.post("/api/theses/generate", json={"holding_id": holding["id"]}, headers=auth_headers)
    thesis_id = gen_response.json()["id"]
    response = await client.put(f"/api/theses/{thesis_id}", json={"status": "active", "conviction": "high"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["conviction"] == "high"


async def test_invalidate_thesis(client, auth_headers, holding):
    mock_output = ThesisOutput(
        bull_case="Test.", key_metrics=[{"metric": "x", "operator": ">=", "threshold": 1, "rationale": "r"}],
        risk_factors="Risk.", suggested_conviction="low",
    )
    with patch("app.routes.thesis.generate_thesis", new_callable=AsyncMock, return_value=mock_output):
        gen = await client.post("/api/theses/generate", json={"holding_id": holding["id"]}, headers=auth_headers)
    thesis_id = gen.json()["id"]
    response = await client.post(f"/api/theses/{thesis_id}/invalidate", json={"reason": "Thesis broken by earnings miss"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "invalidated"
    assert response.json()["invalidation_reason"] == "Thesis broken by earnings miss"
