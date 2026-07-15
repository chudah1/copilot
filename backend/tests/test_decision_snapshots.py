"""Tests for the decision-mirror capture half: snapshot the call + the bet."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.decision_snapshot import DecisionSnapshot
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.decision_snapshots import capture_event_decision, capture_quarterly_decision


async def _setup(db, user_id, *, currency="USD"):
    holding = Holding(
        user_id=user_id, ticker="MSFT", name="Microsoft", quantity=5,
        average_cost_basis=200, current_price=460.0, current_value=1800.0, currency=currency,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=user_id, holding_id=holding.id, status="active", thesis_kind="company",
        why_own_it="Cloud + AI compounding.", confidence="high", review_cadence_days=7,
        interpretation={"monitorability": "high", "watch_hints": [
            {"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 25.0}
        ]},
        source="user",
    )
    db.add(thesis)
    await db.flush()
    return holding, thesis


async def _event(db, holding, thesis, **kw):
    event = MonitoringEvent(
        holding_id=holding.id, thesis_id=thesis.id,
        event_type=kw.get("event_type", "earnings_surprise"),
        evidence_type=kw.get("evidence_type", "earnings"),
        severity=kw.get("severity", "warning"),
        title="MSFT earnings", summary="Azure growth decelerated.",
        evidence_summary=kw.get("evidence_summary", "Azure grew 23%, below your 25% line."),
        claim_id=kw.get("claim_id"), signal_id=kw.get("signal_id"),
        raw_data={"revenue_growth_yoy": 23.0},
    )
    db.add(event)
    await db.flush()
    return event


async def test_capture_records_held_bucket_and_price_context(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    event = await _event(db, holding, thesis)

    snap = await capture_event_decision(db, thesis=thesis, event=event, action="reaffirmed")
    await db.commit()

    assert snap is not None
    assert snap.verdict == "reaffirmed"
    assert snap.bucket == "held"
    assert float(snap.price_native) == 460.0
    assert float(snap.value_gbp) == 1800.0
    assert snap.currency == "USD"
    assert snap.benchmark_ticker == "SPY"
    assert snap.bet_text == "Azure grew 23%, below your 25% line."
    # The condition state is captured for the later reasoning read.
    assert snap.condition_snapshot["triggering_evidence"]["revenue_growth_yoy"] == 23.0
    assert snap.condition_snapshot["watch_hints"][0]["metric"] == "revenue_growth_yoy"
    assert snap.resolved_at is None  # capture only


async def test_bucket_mapping_for_all_verdicts(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    cases = {
        "reaffirmed": "held",
        "lowered_confidence": "held",
        "invalidated": "exited",
        "ignored": "dismissed",
        "not_relevant": "dismissed",
    }
    for verdict, bucket in cases.items():
        event = await _event(db, holding, thesis)
        snap = await capture_event_decision(db, thesis=thesis, event=event, action=verdict)
        assert snap is not None and snap.bucket == bucket
    await db.commit()


async def test_non_verdict_action_is_not_captured(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    event = await _event(db, holding, thesis)
    snap = await capture_event_decision(db, thesis=thesis, event=event, action="some_other_action")
    assert snap is None


async def test_next_test_at_from_future_earnings(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    db.add(EarningsCalendar(ticker="MSFT", report_date=datetime.now(timezone.utc) + timedelta(days=20)))
    await db.flush()
    event = await _event(db, holding, thesis)

    snap = await capture_event_decision(db, thesis=thesis, event=event, action="reaffirmed")
    assert snap.next_test_at is not None


async def test_past_earnings_does_not_anchor_next_test(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    db.add(EarningsCalendar(ticker="MSFT", report_date=datetime.now(timezone.utc) - timedelta(days=5)))
    await db.flush()
    event = await _event(db, holding, thesis)

    snap = await capture_event_decision(db, thesis=thesis, event=event, action="reaffirmed")
    assert snap.next_test_at is None


async def test_benchmark_by_currency(db, test_user):
    holding, thesis = await _setup(db, test_user.id, currency="GBP")
    event = await _event(db, holding, thesis)
    snap = await capture_event_decision(db, thesis=thesis, event=event, action="reaffirmed")
    assert snap.benchmark_ticker == "ISF.L"


async def test_check_in_endpoint_writes_a_snapshot(client, auth_headers, db, test_user):
    """Thesis-level conviction calls moved from the per-event review endpoint
    to the claim check-in — the snapshot now captures one call per sitting."""
    holding, thesis = await _setup(db, test_user.id)
    await _event(db, holding, thesis)
    await db.commit()

    resp = await client.post(
        f"/api/theses/{thesis.id}/claim-reviews",
        json={
            "decisions": [{"claim_id": None, "status": "holds"}],
            "notes": "Still believe Azure re-accelerates.",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200

    snaps = (await db.execute(select(DecisionSnapshot).where(DecisionSnapshot.thesis_id == thesis.id))).scalars().all()
    assert len(snaps) == 1
    assert snaps[0].bucket == "held"
    assert snaps[0].decision_source == "thesis_check_in"
    assert snaps[0].condition_snapshot["verdict_note"] == "Still believe Azure re-accelerates."


# ── Quarterly re-underwrite capture ──────────────────────────────────────────

async def test_quarterly_capture_held_and_exited_buckets(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    cases = {"yes_absolutely": "held", "probably": "held", "not_sure": "held", "no": "exited"}
    for response, bucket in cases.items():
        snap = await capture_quarterly_decision(db, thesis=thesis, holding=holding, response_value=response)
        assert snap is not None
        assert snap.bucket == bucket
        assert snap.decision_source == "quarterly_review"
        assert snap.monitoring_event_id is None  # no triggering event
        assert snap.bet_text == thesis.why_own_it  # the bet is the thesis itself
    await db.commit()


async def test_quarterly_invalid_response_not_captured(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    snap = await capture_quarterly_decision(db, thesis=thesis, holding=holding, response_value="maybe")
    assert snap is None


async def test_quarterly_capture_loads_holding_when_omitted(db, test_user):
    holding, thesis = await _setup(db, test_user.id)
    snap = await capture_quarterly_decision(db, thesis=thesis, response_value="yes_absolutely")
    await db.commit()
    assert snap is not None
    assert snap.holding_id == holding.id
    assert float(snap.price_native) == 460.0
