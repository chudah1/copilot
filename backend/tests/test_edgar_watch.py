import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace
from datetime import datetime, timezone


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


@pytest.mark.asyncio
async def test_edgar_watch_applies_thesis_relevance_filter():
    from app.jobs.edgar_watch import run_edgar_watch

    mock_thesis = MagicMock()
    mock_thesis.id = uuid.uuid4()
    mock_thesis.status = "active"
    mock_thesis.created_at = datetime.now(timezone.utc)
    mock_thesis.why_own_it = "Services flywheel."
    mock_thesis.user_id = uuid.uuid4()

    mock_holding = MagicMock()
    mock_holding.ticker = "AAPL"
    mock_holding.name = "Apple"
    mock_holding.id = uuid.uuid4()
    mock_holding.sector = "Technology"

    fake_claim = SimpleNamespace(id=uuid.uuid4(), claim_text="Services revenue grows", entities=[])
    fake_decomposition = SimpleNamespace(claims=[fake_claim])

    filing = MagicMock()
    filing.items = ["2.02"]

    with patch("app.jobs.edgar_watch.async_session") as mock_session_ctx, \
         patch("app.jobs.edgar_watch.get_recent_8k_filings", new_callable=AsyncMock, return_value=[filing]), \
         patch("app.jobs.edgar_watch.build_edgar_candidates", return_value=[{"event_type": "edgar_8k", "description": "8-K", "evidence": {"headline": "8-K"}}]), \
         patch("app.jobs.edgar_watch.load_active_decomposition", new_callable=AsyncMock, return_value=fake_decomposition), \
         patch("app.jobs.edgar_watch.match_candidates_to_signals", side_effect=lambda candidates, claims: candidates), \
         patch("app.jobs.edgar_watch.enrich_candidates_with_embedding_matches", new_callable=AsyncMock, side_effect=lambda candidates, claims: candidates), \
         patch("app.jobs.edgar_watch.adjudicate_signal_matches", new_callable=AsyncMock, side_effect=lambda candidates, claims: candidates), \
         patch("app.jobs.edgar_watch.filter_candidates_by_thesis_relevance", new_callable=AsyncMock, return_value=[] ) as mock_relevance, \
         patch("app.jobs.edgar_watch.match_thesis_news_watches", new_callable=AsyncMock, return_value={}), \
         patch("app.jobs.edgar_watch.filter_candidates", new_callable=AsyncMock, return_value=[]):

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_thesis, mock_holding)]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_session_ctx.return_value = mock_db

        await run_edgar_watch()

    mock_relevance.assert_awaited_once()
