"""Tests for the hype-buyer climb grounding service + endpoint (Step 3)."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.stress_test import StressTestResult
from app.services.thesis_grounding import build_grounding_payload

_GROUNDING = "app.services.thesis_grounding"


def _stress() -> StressTestResult:
    return StressTestResult(
        ticker="NVDA",
        bear_case="Priced for perfection.",
        key_risks=["Valuation leaves no margin of safety", "Competition intensifies"],
        blind_spots=["No explicit sell rule"],
        what_to_watch=["If revenue growth falls below 8% at next earnings, thesis is at risk"],
        current_price=180.0,
        cached=False,
    )


@pytest.mark.asyncio
async def test_sharp_thesis_skips_grounding_and_stress_test():
    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock) as m_stress, patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock, return_value=None
    ) as m_data:
        payload = await build_grounding_payload(
            ticker="NVDA",
            why_own_it="Margins above 60%, FCF growing and recurring revenue keeps compounding nicely.",
        )

    assert payload.needs_grounding is False
    assert payload.bear_case is None
    m_stress.assert_not_called()  # no wasted stress-test on a sharp thesis
    m_data.assert_not_called()


@pytest.mark.asyncio
async def test_vague_thesis_grounds_with_stress_test():
    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock, return_value=_stress()) as m_stress, patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock, return_value=None
    ):
        payload = await build_grounding_payload(
            ticker="NVDA",
            why_own_it="Everyone was talking about it.",
            investor_profile="hearsay_driven",
            company_name="NVIDIA",
        )

    assert payload.needs_grounding is True
    assert payload.bear_case == "Priced for perfection."
    assert payload.what_to_watch
    assert payload.suggested_questions
    assert any("NVIDIA" in q for q in payload.suggested_questions)
    m_stress.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_thesis_skips_the_paid_stress_test():
    # Blank thesis: still flag for grounding, but don't burn a paid LLM call.
    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock) as m_stress, patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock
    ) as m_data:
        payload = await build_grounding_payload(ticker="NVDA", why_own_it="   ", company_name="NVIDIA")

    assert payload.needs_grounding is True
    assert payload.bear_case is None
    assert payload.suggested_questions
    m_stress.assert_not_called()
    m_data.assert_not_called()


@pytest.mark.asyncio
async def test_broker_ticker_normalized_for_stress_test():
    # The bear case must reference a real symbol, not the raw Trading-212 code.
    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock, return_value=_stress()) as m_stress, patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock, return_value=None
    ):
        await build_grounding_payload(ticker="NVDA_US_EQ", why_own_it="Everyone was talking about it.")

    assert m_stress.await_args.kwargs["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_grounding_survives_market_data_failure():
    # Market data is best-effort; a fetch error must not break the climb.
    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock, return_value=_stress()), patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock, side_effect=RuntimeError("boom")
    ):
        payload = await build_grounding_payload(ticker="NVDA", why_own_it="They make iPhones.")

    assert payload.needs_grounding is True
    assert payload.bear_case == "Priced for perfection."


@pytest.mark.asyncio
async def test_ground_endpoint_returns_payload(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    assert holding.status_code == 201

    with patch(f"{_GROUNDING}.run_stress_test", new_callable=AsyncMock, return_value=_stress()), patch(
        f"{_GROUNDING}.fetch_company_data", new_callable=AsyncMock, return_value=None
    ):
        resp = await client.post(
            "/api/onboarding/ground",
            json={
                "holding_id": holding.json()["id"],
                "investor_profile": "hearsay_driven",
                "why_own_it": "Everyone was talking about it.",
                "what_would_change_my_mind": "Not sure.",
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_grounding"] is True
    assert data["bear_case"] == "Priced for perfection."
    assert data["suggested_questions"]
    assert data["what_to_watch"]


@pytest.mark.asyncio
async def test_ground_endpoint_404_for_unknown_holding(client, auth_headers):
    import uuid

    resp = await client.post(
        "/api/onboarding/ground",
        json={"holding_id": str(uuid.uuid4()), "why_own_it": "Everyone was talking about it."},
        headers=auth_headers,
    )
    assert resp.status_code == 404
