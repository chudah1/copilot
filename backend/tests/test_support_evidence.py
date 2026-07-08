"""Tests for supporting-evidence curation.

The service is straightforward but the cap logic (1 per position, prefer
stronger severity + bound events) is easy to get wrong, so lock the
behaviour in with unit tests before either surface consumes it.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
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


async def _make_signal(db: AsyncSession, thesis: Thesis, label: str) -> ThesisSignal:
    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=1,
        status="confirmed",
    )
    claim = ThesisClaim(
        decomposition=decomposition,
        claim_text=label,
        position=0,
    )
    entity = ThesisEntity(
        claim=claim,
        entity_name="Company",
    )
    signal = ThesisSignal(
        entity=entity,
        signal_type="news_watch",
        signal_label=label,
        active=True,
    )
    db.add(signal)
    await db.flush()
    return signal


async def test_supporting_endpoint_caps_at_one_item_per_position_even_when_limit_is_higher(
    client,
    auth_headers,
    db: AsyncSession,
    test_user: User,
):
    holding = Holding(
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=1,
        average_cost_basis=100,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        holding_id=holding.id,
        user_id=test_user.id,
        status="active",
        why_own_it="CUDA moat remains strong.",
        must_remain_true="Developer lock-in holds.",
        what_would_change_my_mind="CUDA adoption fades.",
    )
    db.add(thesis)
    await db.flush()

    signal = await _make_signal(db, thesis, "CUDA moat commentary")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    db.add_all(
        [
            MonitoringEvent(
                id=uuid.uuid4(),
                holding_id=holding.id,
                thesis_id=thesis.id,
                event_type="gemini_news",
                severity="info",
                title="Support one",
                summary="summary",
                verdict="supports",
                signal_id=signal.id,
                created_at=now,
            ),
            MonitoringEvent(
                id=uuid.uuid4(),
                holding_id=holding.id,
                thesis_id=thesis.id,
                event_type="gemini_news",
                severity="warning",
                title="Support two",
                summary="summary",
                verdict="supports",
                signal_id=signal.id,
                created_at=now,
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        f"/api/monitoring/holdings/{holding.id}/supporting?limit=3",
        headers=auth_headers,
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Support two"


async def test_supporting_endpoint_scopes_to_current_thesis_only(
    client,
    auth_headers,
    db: AsyncSession,
    test_user: User,
):
    holding = Holding(
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=1,
        average_cost_basis=100,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    old_thesis = Thesis(
        holding_id=holding.id,
        user_id=test_user.id,
        status="invalidated",
        why_own_it="Old thesis",
        must_remain_true="Old must",
        what_would_change_my_mind="Old change",
    )
    current_thesis = Thesis(
        holding_id=holding.id,
        user_id=test_user.id,
        status="active",
        why_own_it="Current thesis",
        must_remain_true="Current must",
        what_would_change_my_mind="Current change",
    )
    db.add_all([old_thesis, current_thesis])
    await db.flush()

    signal = await _make_signal(db, current_thesis, "Services growth commentary")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    db.add_all(
        [
            MonitoringEvent(
                id=uuid.uuid4(),
                holding_id=holding.id,
                thesis_id=old_thesis.id,
                event_type="gemini_news",
                severity="thesis_breaking",
                title="Old thesis support",
                summary="summary",
                verdict="supports",
                signal_id=signal.id,
                created_at=now,
            ),
            MonitoringEvent(
                id=uuid.uuid4(),
                holding_id=holding.id,
                thesis_id=current_thesis.id,
                event_type="gemini_news",
                severity="info",
                title="Current thesis support",
                summary="summary",
                verdict="supports",
                signal_id=signal.id,
                created_at=now,
            ),
        ]
    )
    await db.commit()

    response = await client.get(
        f"/api/monitoring/holdings/{holding.id}/supporting",
        headers=auth_headers,
    )
    assert response.status_code == 200
    items = response.json()
    assert [item["title"] for item in items] == ["Current thesis support"]
    assert items[0]["assumption_label"] == "Services growth commentary"
