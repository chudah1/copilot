from unittest.mock import AsyncMock, patch
from app.services.ai_thesis import generate_thesis, ThesisOutput


async def test_generate_thesis_returns_structured_output():
    mock_ai_response = ThesisOutput(
        bull_case="Apple dominates the premium smartphone market with 58% profit share.",
        key_metrics=[
            {"metric": "services_revenue_growth_yoy", "operator": ">=", "threshold": 10.0, "rationale": "Services is the key growth driver"},
            {"metric": "iphone_revenue_share", "operator": ">=", "threshold": 45.0, "rationale": "Core product must maintain dominance"},
        ],
        risk_factors="Regulatory pressure on App Store fees could compress margins.",
        suggested_conviction="high",
    )
    with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, return_value=mock_ai_response):
        result = await generate_thesis(ticker="AAPL", name="Apple Inc", quantity=10, average_cost=150.50)
    assert result.bull_case != ""
    assert len(result.key_metrics) >= 1
    assert result.key_metrics[0]["operator"] in [">=", "<=", ">", "<", "=="]
    assert result.suggested_conviction in ["high", "medium", "low"]


async def test_generate_thesis_handles_ai_failure():
    with patch("app.services.ai_thesis._call_claude", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await generate_thesis(ticker="AAPL", name="Apple Inc", quantity=10, average_cost=150.50)
    assert result is None
