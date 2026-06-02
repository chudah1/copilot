"""Tests for the decision-mirror resolution half — reading back the bet."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.decision_resolution import (
    is_ready,
    resolve_snapshot,
    run_decision_resolution,
)

_RES = "app.services.decision_resolution"
_NOW = datetime(2026, 6, 2, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_benchmark_network():
    """Resolution now fetches a benchmark price for the vs-market read; stub it off
    by default so tests don't hit the network. The relative-read test overrides."""
    with patch(f"{_RES}.fetch_price_on", new_callable=AsyncMock, return_value=None), patch(
        f"{_RES}.fetch_live_price", new_callable=AsyncMock, return_value=None
    ):
        yield


def _company(price=510.0, rev=31.0):
    return SimpleNamespace(
        current_price=price, revenue_growth_yoy=rev,
        earnings_growth_yoy=None, pe_ratio=None, dividend_yield=None,
    )


async def _snapshot(db, user_id, *, bucket="held", verdict="reaffirmed", watch_hints=None,
                    next_test_at=None, decided_at=None, price_native=460.0, claim_id=None,
                    monitoring_event_id=None, bet_text="Azure decel"):
    holding = Holding(user_id=user_id, ticker="MSFT", name="Microsoft", quantity=5,
                      average_cost_basis=200, current_price=460, current_value=1800, currency="USD")
    db.add(holding)
    await db.flush()
    thesis = Thesis(user_id=user_id, holding_id=holding.id, status="active", thesis_kind="company",
                    why_own_it="Cloud + AI.", confidence="high", review_cadence_days=7, source="user")
    db.add(thesis)
    await db.flush()
    snap = DecisionSnapshot(
        user_id=user_id, thesis_id=thesis.id, holding_id=holding.id, verdict=verdict, bucket=bucket,
        decision_source="event_review", decided_at=decided_at or (_NOW - timedelta(days=30)),
        price_native=price_native, value_gbp=1800, currency="USD", benchmark_ticker="SPY",
        next_test_at=next_test_at, bet_text=bet_text, claim_id=claim_id,
        monitoring_event_id=monitoring_event_id,
        condition_snapshot={"watch_hints": watch_hints or []},
    )
    db.add(snap)
    await db.flush()
    return snap, thesis, holding


# ── is_ready ─────────────────────────────────────────────────────────────────

async def test_ready_when_earnings_test_passed(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, next_test_at=_NOW - timedelta(days=1))
    assert is_ready(snap, _NOW) is True


async def test_not_ready_when_earnings_in_future(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, next_test_at=_NOW + timedelta(days=10))
    assert is_ready(snap, _NOW) is False


async def test_soft_read_after_90_days_without_anchor(db, test_user):
    old, *_ = await _snapshot(db, test_user.id, next_test_at=None, decided_at=_NOW - timedelta(days=95))
    fresh, *_ = await _snapshot(db, test_user.id, next_test_at=None, decided_at=_NOW - timedelta(days=10))
    assert is_ready(old, _NOW) is True
    assert is_ready(fresh, _NOW) is False


async def test_already_resolved_is_not_ready(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, next_test_at=_NOW - timedelta(days=1))
    snap.resolved_at = _NOW
    assert is_ready(snap, _NOW) is False


# ── resolve_snapshot: conditions (reasoning read) ────────────────────────────

_HINT = [{"kind": "metric_threshold", "metric": "revenue_growth_yoy", "operator": ">=", "threshold": 25.0}]


async def test_held_with_condition_that_held(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=_HINT,
                               next_test_at=_NOW - timedelta(days=1))
    ok = await resolve_snapshot(db, snap, _company(rev=31.0), now=_NOW)
    assert ok is True
    rj = snap.resolution_json
    assert snap.resolved_at == _NOW
    assert rj["conditions"][0]["held"] is True
    assert "still hold" in rj["read"]


async def test_held_with_condition_that_broke(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=_HINT,
                               next_test_at=_NOW - timedelta(days=1))
    await resolve_snapshot(db, snap, _company(rev=18.0), now=_NOW)
    rj = snap.resolution_json
    assert rj["conditions"][0]["held"] is False
    assert "broken" in rj["read"]


async def test_exited_reasoning_not_regret(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, bucket="exited", verdict="invalidated",
                               watch_hints=_HINT, next_test_at=_NOW - timedelta(days=1))
    await resolve_snapshot(db, snap, _company(rev=18.0), now=_NOW)
    read = snap.resolution_json["read"]
    assert "exited" in read.lower()
    assert "break held up" in read  # frames the reasoning, not price regret


# ── resolve_snapshot: dismissed (attention mirror, claim-linkage) ────────────

async def test_dismissed_claim_broke_after_is_bulletproof_callout(db, test_user):
    import uuid
    claim_id = uuid.uuid4()
    snap, thesis, holding = await _snapshot(
        db, test_user.id, bucket="dismissed", verdict="not_relevant", claim_id=claim_id,
        decided_at=_NOW - timedelta(days=40), next_test_at=_NOW - timedelta(days=1),
    )
    # a later thesis-breaking event on the SAME claim
    db.add(MonitoringEvent(
        holding_id=holding.id, thesis_id=thesis.id, event_type="edgar_8k", severity="thesis_breaking",
        title="t", summary="s", claim_id=claim_id, created_at=_NOW - timedelta(days=5),
    ))
    await db.flush()

    await resolve_snapshot(db, snap, _company(), now=_NOW)
    rj = snap.resolution_json
    assert rj["claim_followthrough"]["broke_after"] is True
    assert "later broke" in rj["read"]


async def test_dismissed_no_followthrough_is_neutral(db, test_user):
    import uuid
    snap, *_ = await _snapshot(db, test_user.id, bucket="dismissed", verdict="not_relevant",
                               claim_id=uuid.uuid4(), next_test_at=_NOW - timedelta(days=1))
    await resolve_snapshot(db, snap, _company(), now=_NOW)
    rj = snap.resolution_json
    assert rj["claim_followthrough"]["broke_after"] is False
    assert "Nothing has followed through" in rj["read"]


async def test_relative_vs_market_read(db, test_user):
    # stock 400 -> 510 = +27.5%; benchmark 100 -> 104 = +4%.
    snap, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=[],
                               next_test_at=_NOW - timedelta(days=1), price_native=400.0)
    with patch(f"{_RES}.fetch_price_on", new_callable=AsyncMock, return_value=100.0), patch(
        f"{_RES}.fetch_live_price", new_callable=AsyncMock, return_value=104.0
    ):
        await resolve_snapshot(db, snap, _company(price=510.0), now=_NOW)
    price = snap.resolution_json["price"]
    assert price["benchmark_pct"] == 4.0
    assert price["relative_pct"] == 23.5
    assert "vs market +4%" in snap.resolution_json["read"]


async def test_vague_thesis_gets_weak_mirror_with_nudge(db, test_user):
    # No metric-threshold condition -> vague -> weak read that nudges for a sharper thesis.
    snap, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=[],
                               next_test_at=_NOW - timedelta(days=1))
    await resolve_snapshot(db, snap, _company(), now=_NOW)
    read = snap.resolution_json["read"]
    assert "wasn't specific enough to test" in read
    assert "pin a measurable condition" in read.lower()


async def test_measurable_thesis_unresolved_this_time_is_not_weak_mirror(db, test_user):
    # Has a metric condition, but the metric isn't in the data yet -> transient
    # "no update", not the vague nudge.
    hint = [{"kind": "metric_threshold", "metric": "pe_ratio", "operator": "<=", "threshold": 30.0}]
    snap, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=hint,
                               next_test_at=_NOW - timedelta(days=1))
    await resolve_snapshot(db, snap, _company(), now=_NOW)  # pe_ratio is None
    read = snap.resolution_json["read"]
    assert "No measurable condition has updated yet" in read
    assert "wasn't specific enough" not in read


async def test_no_market_data_leaves_open_for_retry(db, test_user):
    snap, *_ = await _snapshot(db, test_user.id, next_test_at=_NOW - timedelta(days=1))
    ok = await resolve_snapshot(db, snap, None, now=_NOW)
    assert ok is False
    assert snap.resolved_at is None


# ── the job ──────────────────────────────────────────────────────────────────

async def test_job_resolves_ready_leaves_unready(db, job_session_factory, test_user):
    ready, *_ = await _snapshot(db, test_user.id, bucket="held", watch_hints=_HINT,
                                next_test_at=_NOW - timedelta(days=1))
    pending, *_ = await _snapshot(db, test_user.id, next_test_at=_NOW + timedelta(days=30))
    await db.commit()

    with patch(f"{_RES}.async_session", job_session_factory), patch(
        f"{_RES}.fetch_company_data", new_callable=AsyncMock, return_value=_company(rev=31.0)
    ):
        await run_decision_resolution()

    await db.refresh(ready)
    await db.refresh(pending)
    assert ready.resolved_at is not None
    assert pending.resolved_at is None
