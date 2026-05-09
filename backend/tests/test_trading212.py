import pytest
from unittest.mock import AsyncMock, patch

from app.services.trading212 import Trading212Client, Trading212Position


async def test_fetch_positions_success():
    mock_response_data = [
        {
            "ticker": "AAPL_US_EQ",
            "quantity": 10.0,
            "averagePrice": 150.50,
            "currentPrice": 175.25,
            "ppl": 247.50,
            "fxPpl": 200.0,
        },
        {
            "ticker": "TSLA_US_EQ",
            "quantity": 5.0,
            "averagePrice": 200.00,
            "currentPrice": 250.00,
            "ppl": 250.00,
            "fxPpl": 210.0,
        },
    ]

    client = Trading212Client(api_key="test-key")
    with patch.object(client, "_request", new_callable=AsyncMock, return_value=mock_response_data):
        positions = await client.fetch_positions()

    assert len(positions) == 2
    assert positions[0].ticker == "AAPL_US_EQ"
    assert positions[0].quantity == 10.0
    assert positions[0].average_price == 150.50
    assert positions[0].current_price == 175.25


async def test_fetch_positions_unauthorized():
    client = Trading212Client(api_key="bad-key")
    with patch.object(client, "_request", new_callable=AsyncMock, side_effect=PermissionError("401 Unauthorized")):
        with pytest.raises(PermissionError):
            await client.fetch_positions()
