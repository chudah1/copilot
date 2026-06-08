import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.thesis import Thesis


def test_thesis_has_historical_audit_columns():
    t = Thesis.__table__
    assert "historical_audit_status" in t.c
    assert "historical_audit_results" in t.c


@pytest.mark.asyncio
async def test_run_historical_audit_sets_status_empty_when_no_classified():
    """Happy path with no surviving candidates: status goes pending → empty."""
    thesis_id = uuid.uuid4()

    mock_thesis = MagicMock()
    mock_thesis.id = thesis_id
    mock_thesis.holding_id = uuid.uuid4()
    mock_thesis.interpretation = {}
    mock_thesis.user_id = uuid.uuid4()
    mock_thesis.created_at = datetime.now(timezone.utc)

    mock_holding = MagicMock()
    mock_holding.id = mock_thesis.holding_id
    mock_holding.ticker = "AAPL"
    mock_holding.name = "Apple Inc"
    mock_holding.current_price = 150.0
    mock_holding.sector = "Tech"

    mock_company_data = MagicMock()
    mock_company_data.current_price = 155.0
    mock_company_data.news_items = []

    call_count = [0]

    def execute_side_effect(query):
        result = MagicMock()
        call_count[0] += 1
        # First call → Thesis, second call → Holding
        result.scalar_one_or_none.return_value = mock_thesis if call_count[0] == 1 else mock_holding
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    with (
        patch("app.services.check_now.fetch_company_data", return_value=mock_company_data),
        patch("app.services.check_now.generate_monitoring_candidates", return_value=[]),
        patch("app.services.check_now.get_recent_8k_filings", return_value=[]),
        patch("app.services.check_now.build_edgar_candidates", return_value=[]),
        patch("app.services.check_now.load_active_decomposition", return_value=None),
        patch("app.services.check_now.collect_news_evidence", return_value=[]),
        patch("app.services.check_now.match_candidates_to_signals", return_value=[]),
        patch("app.services.check_now.apply_thesis_floor", return_value=[]),
        patch("app.services.check_now.build_claim_signal_lookup", return_value=({}, {})),
        patch("app.services.check_now.load_investor_profile", return_value=None),
        patch("app.services.check_now.extract_news_watches", return_value=[]),
        patch("app.services.check_now.extract_provisional_news_watches", return_value=[]),
        patch("app.services.check_now.match_thesis_news_watches", return_value=set()),
        patch("app.services.check_now.filter_candidates", return_value=[]),
        patch("app.services.check_now.classify_candidates_for_thesis", return_value=[]),
        patch("app.services.check_now.apply_priority_suppression", return_value=[]),
        patch("app.services.check_now.signal_labels_from_claims", return_value=[]),
    ):
        from app.services.check_now import _run_historical_audit_with_session
        await _run_historical_audit_with_session(mock_db, thesis_id=thesis_id)

    assert mock_thesis.historical_audit_status == "empty"
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_run_historical_audit_sets_failed_on_exception():
    """When pipeline raises, status is set to 'failed' and exception is NOT propagated."""
    thesis_id = uuid.uuid4()

    mock_thesis = MagicMock()
    mock_thesis.id = thesis_id
    mock_thesis.holding_id = uuid.uuid4()

    mock_holding = MagicMock()
    mock_holding.ticker = "AAPL"
    mock_holding.name = "Apple Inc"
    mock_holding.current_price = 150.0

    call_count = [0]

    def execute_side_effect(query):
        result = MagicMock()
        call_count[0] += 1
        result.scalar_one_or_none.return_value = mock_thesis if call_count[0] == 1 else mock_holding
        return result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)

    with patch("app.services.check_now.fetch_company_data", side_effect=RuntimeError("boom")):
        from app.services.check_now import _run_historical_audit_with_session
        # Must not raise
        await _run_historical_audit_with_session(mock_db, thesis_id=thesis_id)

    assert mock_thesis.historical_audit_status == "failed"
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_historical_audit_endpoint_returns_pending_when_status_is_none():
    """Endpoint returns 'pending' when thesis has no audit result yet."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.dependencies import get_current_user

    thesis_id = uuid.uuid4()

    mock_thesis = MagicMock()
    mock_thesis.historical_audit_status = None
    mock_thesis.historical_audit_results = None

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    async def override_get_current_user():
        return mock_user

    with patch("app.routes.thesis._load_user_thesis", return_value=mock_thesis):
        app.dependency_overrides[get_current_user] = override_get_current_user
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(
                    f"/api/theses/{thesis_id}/historical-audit",
                    headers={"Authorization": "Bearer test"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["results"] is None
