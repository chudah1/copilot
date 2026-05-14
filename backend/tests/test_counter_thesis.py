import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.ai_thesis import (
    CounterThesisOutput,
    generate_counter_thesis,
)


@pytest.mark.asyncio
@patch("app.services.ai_thesis.anthropic")
@patch("app.services.ai_thesis.settings")
async def test_counter_thesis_generates_structured_response(mock_settings, mock_anthropic):
    mock_settings.anthropic_api_key = "test-key"

    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(
            text='{"bear_case": "Growth may stall as competition intensifies. The premium valuation leaves little room for error.", "key_risks": ["Competition from Android", "Regulatory scrutiny", "China revenue risk"], "blind_spots": ["Supply chain concentration", "Currency headwinds"], "suggested_additions": ["Exit if services growth drops below 10%", "Review if PE exceeds 35x"]}'
        )
    ]
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.AsyncAnthropic.return_value = mock_client

    result = await generate_counter_thesis(
        why_own_it="I own Apple for ecosystem strength.",
        must_remain_true="Services growth stays healthy.",
        what_would_change_my_mind="Margin compression without recovery.",
        ai_summary="Apple is held for ecosystem durability.",
        ticker="AAPL",
    )

    assert isinstance(result, CounterThesisOutput)
    assert "stall" in result.bear_case.lower() or "competition" in result.bear_case.lower()
    assert len(result.key_risks) == 3
    assert len(result.blind_spots) == 2
    assert len(result.suggested_additions) == 2


@pytest.mark.asyncio
async def test_counter_thesis_endpoint_404(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/theses/{fake_id}/counter-thesis", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("app.services.ai_thesis.settings")
async def test_counter_thesis_fallback_when_no_api_key(mock_settings):
    mock_settings.anthropic_api_key = ""

    result = await generate_counter_thesis(
        why_own_it="Strong growth in cloud computing and AI demand.",
        must_remain_true="Cloud revenue keeps growing.",
        what_would_change_my_mind="Growth stalls.",
        ai_summary="Held for cloud and AI growth.",
        ticker="MSFT",
    )

    assert isinstance(result, CounterThesisOutput)
    assert "MSFT" in result.bear_case
    assert len(result.key_risks) >= 3
    assert len(result.blind_spots) >= 2
    assert len(result.suggested_additions) >= 2
    # Growth label should be detected from the thesis text
    assert any("growth" in r.lower() for r in result.key_risks)


@pytest.mark.asyncio
@patch("app.routes.thesis.generate_counter_thesis", new_callable=AsyncMock)
async def test_counter_thesis_endpoint_success(mock_generate, client, auth_headers, test_user, db):
    mock_generate.return_value = CounterThesisOutput(
        bear_case="The bull case may be overly optimistic.",
        key_risks=["Competition", "Regulatory risk", "Valuation risk"],
        blind_spots=["Supply chain risk", "Currency risk"],
        suggested_additions=["Set a PE ceiling", "Define growth floor"],
    )

    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=20, average_cost_basis=96, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI hardware play",
        must_remain_true="Revenue keeps growing",
        what_would_change_my_mind="Growth stalls",
        confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.post(f"/api/theses/{thesis.id}/counter-thesis", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["thesis_id"] == str(thesis.id)
    assert data["bear_case"] == "The bull case may be overly optimistic."
    assert len(data["key_risks"]) == 3
    assert len(data["blind_spots"]) == 2
    assert len(data["suggested_additions"]) == 2
    assert "generated_at" in data
