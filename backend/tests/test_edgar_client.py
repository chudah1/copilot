import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services import edgar


def _empty_submissions() -> dict:
    return {
        "filings": {
            "recent": {
                "form": [],
                "filingDate": [],
                "accessionNumber": [],
                "primaryDocument": [],
                "items": [],
            }
        }
    }


@pytest.fixture(autouse=True)
def clear_edgar_caches():
    edgar._submissions_cache.clear()
    edgar._submissions_inflight.clear()
    yield
    edgar._submissions_cache.clear()
    edgar._submissions_inflight.clear()


@pytest.mark.asyncio
async def test_8k_and_form4_share_one_submissions_fetch():
    request_json = AsyncMock(return_value=_empty_submissions())

    with (
        patch("app.services.edgar.get_cik_for_ticker", new=AsyncMock(return_value="320193")),
        patch("app.services.edgar._request_json", new=request_json),
    ):
        await edgar.get_recent_8k_filings("AAPL", since=date(2026, 7, 1))
        await edgar.get_recent_form4_transactions("AAPL", since=date(2026, 7, 1))

    request_json.assert_awaited_once_with(
        "https://data.sec.gov/submissions/CIK0000320193.json"
    )


@pytest.mark.asyncio
async def test_concurrent_requests_for_same_cik_are_coalesced():
    release = asyncio.Event()

    async def slow_response(_url: str) -> dict:
        await release.wait()
        return _empty_submissions()

    request_json = AsyncMock(side_effect=slow_response)

    with (
        patch("app.services.edgar.get_cik_for_ticker", new=AsyncMock(return_value="1045810")),
        patch("app.services.edgar._request_json", new=request_json),
    ):
        first = asyncio.create_task(
            edgar.get_recent_8k_filings("NVDA", since=date(2026, 7, 1))
        )
        second = asyncio.create_task(
            edgar.get_recent_8k_filings("NVDA", since=date(2026, 7, 1))
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)

    assert request_json.await_count == 1


@pytest.mark.asyncio
async def test_request_retries_429_and_honours_retry_after():
    request = httpx.Request("GET", "https://data.sec.gov/example.json")
    responses = [
        httpx.Response(429, headers={"Retry-After": "2"}, request=request),
        httpx.Response(200, json={"ok": True}, request=request),
    ]
    client = AsyncMock()
    client.get = AsyncMock(side_effect=responses)
    sleep = AsyncMock()

    with (
        patch("app.services.edgar._get_http_client", new=AsyncMock(return_value=client)),
        patch("app.services.edgar._wait_for_request_slot", new=AsyncMock()),
        patch("app.services.edgar.asyncio.sleep", new=sleep),
    ):
        result = await edgar._request_json("https://data.sec.gov/example.json")

    assert result == {"ok": True}
    assert client.get.await_count == 2
    sleep.assert_awaited_once_with(2.0)


@pytest.mark.asyncio
async def test_request_does_not_retry_non_transient_4xx():
    request = httpx.Request("GET", "https://data.sec.gov/missing.json")
    client = AsyncMock()
    client.get = AsyncMock(
        return_value=httpx.Response(404, request=request)
    )

    with (
        patch("app.services.edgar._get_http_client", new=AsyncMock(return_value=client)),
        patch("app.services.edgar._wait_for_request_slot", new=AsyncMock()),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await edgar._request_json("https://data.sec.gov/missing.json")

    client.get.assert_awaited_once()
