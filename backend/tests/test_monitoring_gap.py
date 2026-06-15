import uuid
import pytest
from unittest.mock import AsyncMock

from app.models.monitoring_gap import MonitoringGap

def test_monitoring_gap_model_importable():
    from app.models.monitoring_gap import MonitoringGap
    assert MonitoringGap.__tablename__ == "monitoring_gaps"


@pytest.mark.asyncio
async def test_write_monitoring_gap_inserts_row(db):
    from app.services.monitoring_gap_writer import write_monitoring_gap

    thesis_id = uuid.uuid4()
    run_id = str(uuid.uuid4())

    await write_monitoring_gap(db, thesis_id, "gemini_news", "timeout", run_id)

    rows = (
        await db.execute(
            MonitoringGap.__table__.select().where(MonitoringGap.thesis_id == thesis_id)
        )
    ).all()
    assert len(rows) == 1
    added = rows[0]
    assert added.source == "gemini_news"
    assert added.error_message == "timeout"
    assert added.thesis_id == thesis_id
    assert added.run_id == run_id


@pytest.mark.asyncio
async def test_edgar_exception_propagates():
    """get_recent_8k_filings should raise on EDGAR network error so callers can write a gap."""
    import httpx
    from unittest.mock import patch, AsyncMock

    with patch("app.services.edgar.get_cik_for_ticker", new=AsyncMock(return_value="0001234567")):
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.get.side_effect = httpx.ReadTimeout("timeout")
            mock_client.return_value = mock_instance

            from app.services.edgar import get_recent_8k_filings
            with pytest.raises(Exception):
                await get_recent_8k_filings("NVDA")


@pytest.mark.asyncio
async def test_write_monitoring_gap_skips_invalid_source():
    from app.services.monitoring_gap_writer import write_monitoring_gap

    db = AsyncMock()
    thesis_id = uuid.uuid4()

    await write_monitoring_gap(db, thesis_id, "unknown_source", "some error", "run123")

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_gaps_endpoint_returns_list(client, auth_headers):
    """GET /api/monitoring/gaps returns an empty list when no gaps exist."""
    resp = await client.get("/api/monitoring/gaps", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
