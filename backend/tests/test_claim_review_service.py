from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.claim_review import ClaimReview
from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_review import ThesisReview
from app.models.thesis_signal import ThesisSignal
from app.services.claim_review import (
    GENERAL_BUCKET,
    compute_check_in,
    submit_claim_reviews,
)


async def _make_thesis(db, test_user, *, with_decomposition=True):
    holding = Holding(
        user_id=test_user.id,
        ticker="NOW",
        name="ServiceNow",
        quantity=1,
        average_cost_basis=100,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Workflow lock-in plus AI upsell.",
        must_remain_true="Subscription revenue keeps growing above 20%.",
        what_would_change_my_mind="Customers stop expanding their spending.",
        confidence="high",
        review_cadence_days=30,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    claim = signal = None
    if with_decomposition:
        decomposition = ThesisDecomposition(thesis_id=thesis.id, version=1, status="confirmed")
        db.add(decomposition)
        await db.flush()
        claim = ThesisClaim(
            decomposition_id=decomposition.id,
            claim_text="Subscription revenue keeps growing above 20%",
            raw_extraction_json={"source_field": "must_remain_true"},
            position=0,
        )
        db.add(claim)
        await db.flush()
        entity = ThesisEntity(claim_id=claim.id, entity_name="ServiceNow")
        db.add(entity)
        await db.flush()
        signal = ThesisSignal(
            entity_id=entity.id,
            signal_type="metric",
            signal_label="NOW subscription revenue growth",
            active=True,
        )
        db.add(signal)
        await db.flush()
    return holding, thesis, claim, signal


def _event(thesis, holding, *, severity="warning", verdict="threatens", claim_id=None, signal_id=None, created_at=None):
    return MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity=severity,
        title="Event",
        summary="Summary",
        verdict=verdict,
        claim_id=claim_id,
        signal_id=signal_id,
        created_at=created_at or datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_signal_bound_event_resolves_to_parent_claim(db, test_user):
    holding, thesis, claim, signal = await _make_thesis(db, test_user)
    db.add(_event(thesis, holding, signal_id=signal.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    claim_state = next(s for s in states if s.claim_id == claim.id)
    assert len(claim_state.threatens_events) == 1
    assert claim_state.case_section == "must_remain_true"


@pytest.mark.asyncio
async def test_supports_evidence_never_triggers_review(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    for _i in range(5):
        db.add(_event(thesis, holding, severity="info", verdict="supports", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    claim_state = next(s for s in states if s.claim_id == claim.id)
    assert claim_state.needs_review is False
    assert len(claim_state.supports_events) == 5


@pytest.mark.asyncio
async def test_thesis_breaking_event_asks_immediately(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    db.add(_event(thesis, holding, severity="thesis_breaking", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    claim_state = next(s for s in states if s.claim_id == claim.id)
    assert claim_state.needs_review is True


@pytest.mark.asyncio
async def test_warning_threatens_threshold_is_two(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    db.add(_event(thesis, holding, severity="warning", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    assert next(s for s in states if s.claim_id == claim.id).needs_review is False

    db.add(_event(thesis, holding, severity="warning", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    assert next(s for s in states if s.claim_id == claim.id).needs_review is True


@pytest.mark.asyncio
async def test_any_threatens_threshold_is_four(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    for _i in range(3):
        db.add(_event(thesis, holding, severity="info", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    assert next(s for s in states if s.claim_id == claim.id).needs_review is False

    db.add(_event(thesis, holding, severity="info", claim_id=claim.id))
    await db.commit()

    states = await compute_check_in(db, thesis)
    assert next(s for s in states if s.claim_id == claim.id).needs_review is True


@pytest.mark.asyncio
async def test_flagged_events_are_excluded(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    event_one = _event(thesis, holding, severity="warning", claim_id=claim.id)
    event_two = _event(thesis, holding, severity="warning", claim_id=claim.id)
    db.add_all([event_one, event_two])
    await db.flush()
    db.add(
        ThesisReview(
            thesis_id=thesis.id,
            monitoring_event_id=event_one.id,
            action="not_relevant",
        )
    )
    await db.commit()

    states = await compute_check_in(db, thesis)
    claim_state = next(s for s in states if s.claim_id == claim.id)
    assert len(claim_state.threatens_events) == 1
    assert claim_state.needs_review is False


@pytest.mark.asyncio
async def test_events_before_last_review_are_excluded(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    now = datetime.now(timezone.utc)
    db.add(_event(thesis, holding, severity="warning", claim_id=claim.id, created_at=now - timedelta(days=3)))
    db.add(_event(thesis, holding, severity="warning", claim_id=claim.id, created_at=now - timedelta(days=3)))
    db.add(
        ClaimReview(
            thesis_id=thesis.id,
            claim_id=claim.id,
            session_id=uuid.uuid4(),
            status="holds",
            created_at=now - timedelta(days=1),
        )
    )
    await db.commit()

    states = await compute_check_in(db, thesis)
    claim_state = next(s for s in states if s.claim_id == claim.id)
    assert claim_state.needs_review is False
    assert claim_state.threatens_events == []
    assert claim_state.status == "holds"
    assert claim_state.last_reviewed_at is not None


@pytest.mark.asyncio
async def test_unbound_events_land_in_general_bucket(db, test_user):
    holding, thesis, _claim, _ = await _make_thesis(db, test_user)
    db.add(_event(thesis, holding, severity="thesis_breaking"))
    await db.commit()

    states = await compute_check_in(db, thesis)
    general = next(s for s in states if s.claim_id is None)
    assert general.label == GENERAL_BUCKET
    assert general.needs_review is True


@pytest.mark.asyncio
async def test_thesis_without_decomposition_gets_single_bucket(db, test_user):
    holding, thesis, _claim, _ = await _make_thesis(db, test_user, with_decomposition=False)
    db.add(_event(thesis, holding, severity="warning"))
    await db.commit()

    states = await compute_check_in(db, thesis)
    assert len(states) == 1
    assert states[0].claim_id is None


@pytest.mark.asyncio
async def test_submit_writes_rows_and_conviction_log(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    await db.commit()

    session_id = await submit_claim_reviews(
        db,
        thesis=thesis,
        holding=holding,
        user_id=test_user.id,
        decisions=[{"claim_id": claim.id, "status": "holds", "notes": None}],
    )
    await db.commit()

    rows = (await db.execute(ClaimReview.__table__.select())).all()
    assert len(rows) == 1
    assert rows[0].session_id == session_id
    log_rows = (await db.execute(ConvictionLogEntry.__table__.select())).all()
    assert len(log_rows) == 1


@pytest.mark.asyncio
async def test_submit_broken_requires_thesis_action(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    await db.commit()

    with pytest.raises(ValueError):
        await submit_claim_reviews(
            db,
            thesis=thesis,
            holding=holding,
            user_id=test_user.id,
            decisions=[{"claim_id": claim.id, "status": "broken", "notes": None}],
        )


@pytest.mark.asyncio
async def test_submit_broken_with_invalidate_invalidates_thesis(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    await db.commit()

    await submit_claim_reviews(
        db,
        thesis=thesis,
        holding=holding,
        user_id=test_user.id,
        decisions=[{"claim_id": claim.id, "status": "broken", "notes": "Growth stalled"}],
        thesis_action="invalidate",
    )
    await db.commit()

    assert thesis.status == "invalidated"
    assert thesis.invalidated_at is not None


@pytest.mark.asyncio
async def test_submit_captures_decision_snapshot(db, test_user):
    from app.models.decision_snapshot import DecisionSnapshot

    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    await db.commit()

    await submit_claim_reviews(
        db,
        thesis=thesis,
        holding=holding,
        user_id=test_user.id,
        decisions=[{"claim_id": claim.id, "status": "holds", "notes": None}],
    )
    await db.commit()

    snaps = (await db.execute(DecisionSnapshot.__table__.select())).all()
    assert len(snaps) == 1
    assert snaps[0].bucket == "held"
    assert snaps[0].decision_source == "thesis_check_in"
    assert snaps[0].bet_text == "Subscription revenue keeps growing above 20%"


@pytest.mark.asyncio
async def test_submit_broken_with_keep_lowered_downgrades_confidence(db, test_user):
    holding, thesis, claim, _ = await _make_thesis(db, test_user)
    await db.commit()

    await submit_claim_reviews(
        db,
        thesis=thesis,
        holding=holding,
        user_id=test_user.id,
        decisions=[{"claim_id": claim.id, "status": "broken", "notes": None}],
        thesis_action="keep_lowered",
    )
    await db.commit()

    assert thesis.confidence == "medium"
    assert thesis.status == "active"
