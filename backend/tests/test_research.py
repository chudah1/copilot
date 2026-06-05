from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.stress_test import (
    CandidateSignal,
    StressTestResult,
    StressTestRiskGroup,
    StressTestSourceNote,
)


@pytest.mark.asyncio
async def test_stress_test_endpoint_returns_grouped_and_cited_payload(client):
    mock_company = SimpleNamespace(currency="USD")
    mock_result = StressTestResult(
        ticker="MU",
        bear_case="HBM demand could cool faster than the market expects.",
        key_risks=["Valuation leaves little margin of safety", "Competition could erode pricing"],
        risk_groups=[
            StressTestRiskGroup(category="Financial risk", items=["Valuation leaves little margin of safety"]),
            StressTestRiskGroup(category="Competitive risk", items=["Competition could erode pricing"]),
        ],
        blind_spots=["No explicit customer concentration check"],
        what_to_watch=["If revenue growth falls below 10% at next earnings, the case weakens."],
        current_price=122.4,
        cached=False,
        source_notes=[
            StressTestSourceNote(label="Valuation", detail="P/E ratio 28.4x", source="Company overview"),
            StressTestSourceNote(label="Recent news", detail="Micron expands HBM output", source="Reuters", url="https://example.com"),
        ],
        candidate_signals=[
            CandidateSignal(
                signal_type="revenue_growth",
                label="Revenue growth stays above 10%",
                threshold_pct=10.0,
                rationale="The demand case needs sustained growth.",
                operator=">=",
            )
        ],
    )

    with patch("app.routes.research.fetch_company_data", new_callable=AsyncMock, return_value=mock_company), patch(
        "app.routes.research.run_stress_test", new_callable=AsyncMock, return_value=mock_result
    ):
        response = await client.post(
            "/api/research/stress-test",
            json={"ticker": "MU", "draft_thesis": "HBM demand stays strong."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["risk_groups"][0]["category"] == "Financial risk"
    assert data["source_notes"][0]["label"] == "Valuation"
    assert data["candidate_signals"][0]["signal_type"] == "revenue_growth"
