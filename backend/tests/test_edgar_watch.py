import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_edgar_watch_writes_gap_on_failure():
    """If get_recent_8k_filings raises, edgar_watch writes a MonitoringGap."""
    from app.jobs.edgar_watch import run_edgar_watch

    mock_thesis = MagicMock()
    mock_thesis.id = uuid.uuid4()
    mock_thesis.status = "active"

    mock_holding = MagicMock()
    mock_holding.ticker = "NVDA"

    with patch("app.jobs.edgar_watch.async_session") as mock_session_ctx, \
         patch("app.jobs.edgar_watch.get_recent_8k_filings", side_effect=Exception("timeout")), \
         patch("app.jobs.edgar_watch.write_monitoring_gap", new=AsyncMock()) as mock_write_gap:

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_thesis, mock_holding)]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.return_value = mock_db

        await run_edgar_watch()
        mock_write_gap.assert_called_once()
        assert mock_write_gap.call_args[0][2] == "edgar"
        mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_edgar_watch_only_processes_high_materiality_items():
    """edgar_watch filters to high-materiality 8-K items only."""
    from app.jobs.edgar_watch import HIGH_MATERIALITY_ITEMS
    assert "2.02" in HIGH_MATERIALITY_ITEMS  # Earnings release
    assert "1.03" in HIGH_MATERIALITY_ITEMS  # Bankruptcy
    assert "5.02" not in HIGH_MATERIALITY_ITEMS  # Exec change — low materiality for hourly
    assert "7.01" not in HIGH_MATERIALITY_ITEMS  # Guidance — waits for daily run
