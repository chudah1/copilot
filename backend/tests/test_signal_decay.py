import uuid

import pytest

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.auth import hash_password
from app.services.monitoring_review import review_monitoring_event


async def _setup_holding_with_signal(db):
    """Create a user, holding, thesis, decomposition, and one active signal."""
    user = User(email="decay@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=100,
        current_price=150,
        current_value=1500,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem demand.",
        confidence="high",
        review_cadence_days=7,
        source="user",
        interpretation={
            "labels": ["growth"],
            "monitorability": "high",
            "watch_hints": [
                {"kind": "price_move_pct", "threshold": 5.0, "signal_id": "placeholder", "claim_id": "placeholder"},
            ],
            "proxy_signals": [],
            "ambiguity_note": "",
        },
    )
    db.add(thesis)
    await db.flush()

    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=1,
        status="confirmed",
        reason_type="growth",
        monitorability="high",
    )
    db.add(decomposition)
    await db.flush()

    claim = ThesisClaim(
        decomposition_id=decomposition.id,
        claim_text="Customer demand remains strong",
        claim_type="growth",
        position=1,
    )
    db.add(claim)
    await db.flush()

    entity = ThesisEntity(
        claim_id=claim.id,
        entity_name="Apple",
        entity_ticker="AAPL",
        entity_type="held_company",
        user_confirmed=True,
    )
    db.add(entity)
    await db.flush()

    signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="price_move",
        signal_label="Price movement >5%",
        signal_config_json={"threshold_pct": 5.0},
        active=True,
        user_confirmed=True,
        consecutive_ignores=0,
    )
    db.add(signal)
    await db.flush()

    # Update interpretation with real IDs
    thesis.interpretation["watch_hints"][0]["signal_id"] = str(signal.id)
    thesis.interpretation["watch_hints"][0]["claim_id"] = str(claim.id)

    await db.commit()
    return user, holding, thesis, signal, claim


def _make_event(holding, thesis, signal, claim_id=None):
    return MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title=f"Review {holding.ticker}",
        summary="Price moved 8% since last check.",
        signal_id=signal.id,
        claim_id=claim_id,
        evidence_type="price_move",
        verdict="review",
    )


@pytest.mark.asyncio
async def test_ignored_increments_consecutive_ignores(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 1
    assert signal.active is True


@pytest.mark.asyncio
async def test_not_relevant_increments_consecutive_ignores(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="not_relevant", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 1
    assert signal.active is True


@pytest.mark.asyncio
async def test_reaffirmed_resets_consecutive_ignores(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)
    signal.consecutive_ignores = 2
    await db.commit()

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="reaffirmed", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 0


@pytest.mark.asyncio
async def test_lowered_confidence_resets_consecutive_ignores(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)
    signal.consecutive_ignores = 2
    await db.commit()

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="lowered_confidence", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 0


@pytest.mark.asyncio
async def test_signal_deactivated_at_threshold(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)
    signal.consecutive_ignores = 2  # One more ignore triggers deactivation
    await db.commit()

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 3
    assert signal.active is False


@pytest.mark.asyncio
async def test_interpretation_cache_rebuilt_on_deactivation(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)
    signal.consecutive_ignores = 2
    await db.commit()

    # Verify thesis has watch_hints before
    assert thesis.interpretation is not None
    assert len(thesis.interpretation.get("watch_hints", [])) == 1

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)

    await db.refresh(thesis)
    # With no active signals remaining, interpretation should be None
    assert thesis.interpretation is None


@pytest.mark.asyncio
async def test_no_signal_id_on_event_skips_decay(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)

    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="Review AAPL",
        summary="Price moved.",
        signal_id=None,  # No signal linked
    )
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 0  # Unchanged


@pytest.mark.asyncio
async def test_already_inactive_signal_not_double_deactivated(db):
    user, holding, thesis, signal, claim = await _setup_holding_with_signal(db)
    signal.consecutive_ignores = 5
    signal.active = False
    await db.commit()

    event = _make_event(holding, thesis, signal, claim_id=claim.id)
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)

    await db.refresh(signal)
    assert signal.consecutive_ignores == 6
    assert signal.active is False
