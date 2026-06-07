import uuid
import pytest
from unittest.mock import AsyncMock

def test_monitoring_gap_model_importable():
    from app.models.monitoring_gap import MonitoringGap
    assert MonitoringGap.__tablename__ == "monitoring_gaps"


@pytest.mark.asyncio
async def test_write_monitoring_gap_inserts_row():
    from app.services.monitoring_gap_writer import write_monitoring_gap

    db = AsyncMock()
    thesis_id = uuid.uuid4()
    run_id = str(uuid.uuid4())

    await write_monitoring_gap(db, thesis_id, "gemini_news", "timeout", run_id)

    db.add.assert_called_once()
    added = db.add.call_args[0][0]
    assert added.source == "gemini_news"
    assert added.error_message == "timeout"
    assert added.thesis_id == thesis_id
    assert added.run_id == run_id
