"""Tests for supporting-evidence curation.

The service is straightforward but the cap logic (1 per position, prefer
stronger severity + bound events) is easy to get wrong, so lock the
behaviour in with unit tests before either surface consumes it.
"""
import uuid
from datetime import datetime, timezone

from app.models.monitoring_event import MonitoringEvent
from app.services.support_evidence import curate_supporting_items


def _event(
    *,
    holding_id: uuid.UUID,
    severity: str = "info",
    claim_id: uuid.UUID | None = None,
    signal_id: uuid.UUID | None = None,
    minutes_ago: int = 0,
    title: str = "Positive news",
) -> MonitoringEvent:
    now = datetime.now(timezone.utc)
    event = MonitoringEvent(
        id=uuid.uuid4(),
        holding_id=holding_id,
        thesis_id=uuid.uuid4(),
        event_type="gemini_news",
        severity=severity,
        title=title,
        summary="",
        verdict="supports",
        claim_id=claim_id,
        signal_id=signal_id,
    )
    event.created_at = now.replace(microsecond=0)
    return event


def test_curate_caps_at_one_per_position_by_default():
    holding = uuid.uuid4()
    tickers = {holding: "NVDA"}
    events = [
        _event(holding_id=holding, title="First supports"),
        _event(holding_id=holding, title="Second supports"),
        _event(holding_id=holding, title="Third supports"),
    ]
    picked = curate_supporting_items(events, ticker_by_holding=tickers, max_items=5)
    assert len(picked) == 1


def test_curate_respects_max_total_across_positions():
    hn, ha, hm = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tickers = {hn: "NVDA", ha: "AAPL", hm: "MSFT"}
    events = [
        _event(holding_id=hn),
        _event(holding_id=ha),
        _event(holding_id=hm),
    ]
    picked = curate_supporting_items(events, ticker_by_holding=tickers, max_items=2)
    assert len(picked) == 2
    assert len({item.ticker for item in picked}) == 2


def test_curate_prefers_stronger_severity_over_older_info():
    holding = uuid.uuid4()
    ha = uuid.uuid4()
    tickers = {holding: "NVDA", ha: "AAPL"}
    events = [
        _event(holding_id=holding, severity="thesis_breaking", title="Major"),
        _event(holding_id=ha, severity="info", title="Routine"),
    ]
    picked = curate_supporting_items(events, ticker_by_holding=tickers, max_items=1)
    # The stronger positive wins, not the routine info-tier one on a
    # different holding.
    assert picked[0].title == "Major"


def test_curate_prefers_bound_events_over_unbound():
    ha, hb = uuid.uuid4(), uuid.uuid4()
    tickers = {ha: "AAPL", hb: "MSFT"}
    events = [
        _event(holding_id=ha, claim_id=uuid.uuid4(), signal_id=uuid.uuid4(), title="Bound"),
        _event(holding_id=hb, title="Unbound"),  # same severity, no binding
    ]
    picked = curate_supporting_items(events, ticker_by_holding=tickers, max_items=1)
    assert picked[0].title == "Bound"


def test_curate_returns_empty_when_no_events():
    assert curate_supporting_items([], ticker_by_holding={}) == []


def test_curate_skips_events_whose_holding_has_no_ticker_mapping():
    holding = uuid.uuid4()
    events = [_event(holding_id=holding)]
    # ticker_by_holding is empty — the digest / API caller didn't include
    # this holding, so it should be dropped rather than surfaced with a
    # blank ticker.
    picked = curate_supporting_items(events, ticker_by_holding={})
    assert picked == []
