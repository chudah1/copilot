import uuid

import pytest
from sqlalchemy import select

from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.auth import hash_password
from app.services.conviction_log import (
    EVIDENCE_REVIEWED,
    MANUAL_NOTE,
    REASON_CREATED,
    REASON_INVALIDATED,
    REASON_UPDATED,
    SIGNAL_CONFIRMED,
    SIGNAL_REMOVED,
    SIGNALS_GENERATED,
    append_log_entry,
)


async def _create_user(db, email="log@example.com"):
    user = User(email=email, password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()
    return user


async def _create_holding(db, user):
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
    return holding


async def _create_thesis(db, user, holding, **kwargs):
    defaults = dict(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Strong ecosystem demand.",
        confidence="high",
        review_cadence_days=7,
        source="user",
    )
    defaults.update(kwargs)
    thesis = Thesis(**defaults)
    db.add(thesis)
    await db.flush()
    return thesis


# ---------------------------------------------------------------------------
# Service: append_log_entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_log_entry_creates_record(db):
    user = await _create_user(db)
    holding = await _create_holding(db, user)
    thesis = await _create_thesis(db, user, holding)

    entry = append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=user.id,
        entry_type=REASON_CREATED,
        content="Test reason",
        metadata={"confidence": "high"},
    )
    await db.commit()
    await db.refresh(entry)

    assert entry.id is not None
    assert entry.entry_type == REASON_CREATED
    assert entry.content == "Test reason"
    assert entry.metadata_json == {"confidence": "high"}
    assert entry.thesis_id == thesis.id
    assert entry.holding_id == holding.id
    assert entry.user_id == user.id


@pytest.mark.asyncio
async def test_append_log_entry_with_signal_and_claim(db):
    user = await _create_user(db)
    holding = await _create_holding(db, user)
    thesis = await _create_thesis(db, user, holding)
    signal_id = uuid.uuid4()
    claim_id = uuid.uuid4()

    entry = append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=user.id,
        entry_type=SIGNAL_CONFIRMED,
        content="Confirmed: Price movement >5%",
        signal_id=signal_id,
        claim_id=claim_id,
    )
    await db.commit()
    await db.refresh(entry)

    assert entry.signal_id == signal_id
    assert entry.claim_id == claim_id


# ---------------------------------------------------------------------------
# Hook: thesis creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thesis_creation_logs_reason_created(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    await db.commit()

    response = await client.post(
        "/api/theses",
        json={
            "holding_id": str(holding.id),
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "I believe in Apple's ecosystem.",
            "confidence": "high",
            "review_cadence_days": 7,
            "source": "user",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.holding_id == holding.id,
            ConvictionLogEntry.entry_type == REASON_CREATED,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.content == "I believe in Apple's ecosystem."


# ---------------------------------------------------------------------------
# Hook: evidence reviewed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_review_logs_entry(db):
    from app.services.monitoring_review import review_monitoring_event

    user = await _create_user(db, email="review_log@example.com")
    holding = await _create_holding(db, user)
    thesis = await _create_thesis(db, user, holding)

    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="Review AAPL",
        summary="Price moved 8% since last check.",
    )
    db.add(event)
    await db.commit()

    await review_monitoring_event(db, event=event, thesis=thesis, action="reaffirmed", notes="Still holding")

    result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.thesis_id == thesis.id,
            ConvictionLogEntry.entry_type == EVIDENCE_REVIEWED,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert "reaffirmed" in entry.content
    assert entry.metadata_json["action"] == "reaffirmed"
    assert entry.metadata_json["notes"] == "Still holding"


# ---------------------------------------------------------------------------
# Hook: thesis invalidation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thesis_invalidation_logs_entry(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    thesis = await _create_thesis(db, test_user, holding)
    await db.commit()

    response = await client.post(
        f"/api/theses/{thesis.id}/invalidate",
        json={"reason": "Thesis no longer valid"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.thesis_id == thesis.id,
            ConvictionLogEntry.entry_type == REASON_INVALIDATED,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.content == "Thesis no longer valid"


# ---------------------------------------------------------------------------
# Hook: thesis update (why_own_it changed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_thesis_update_logs_reason_updated(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    thesis = await _create_thesis(db, test_user, holding)
    await db.commit()

    response = await client.put(
        f"/api/theses/{thesis.id}",
        json={"why_own_it": "Updated reason: stronger moat"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.thesis_id == thesis.id,
            ConvictionLogEntry.entry_type == REASON_UPDATED,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.content == "Updated reason: stronger moat"


@pytest.mark.asyncio
async def test_thesis_update_no_log_when_reason_unchanged(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    thesis = await _create_thesis(db, test_user, holding)
    await db.commit()

    # Update confidence only — no reason_updated log
    response = await client.put(
        f"/api/theses/{thesis.id}",
        json={"confidence": "low"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    result = await db.execute(
        select(ConvictionLogEntry).where(
            ConvictionLogEntry.thesis_id == thesis.id,
            ConvictionLogEntry.entry_type == REASON_UPDATED,
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is None


# ---------------------------------------------------------------------------
# API: GET conviction log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_conviction_log(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    thesis = await _create_thesis(db, test_user, holding)

    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=test_user.id,
        entry_type=REASON_CREATED,
        content="Original reason",
    )
    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=test_user.id,
        entry_type=MANUAL_NOTE,
        content="My thoughts on Q1",
    )
    await db.commit()

    response = await client.get(
        f"/api/portfolio/holdings/{holding.id}/conviction-log",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["entries"]) == 2
    assert data["reason_age_days"] is not None
    assert data["reason_age_days"] >= 0
    assert data["review_count"] == 0
    entry_types = {e["entry_type"] for e in data["entries"]}
    assert REASON_CREATED in entry_types
    assert MANUAL_NOTE in entry_types


@pytest.mark.asyncio
async def test_get_conviction_log_not_found_for_other_user(client, db, test_user, auth_headers):
    other_user = await _create_user(db, email="other@example.com")
    holding = await _create_holding(db, other_user)
    await db.commit()

    response = await client.get(
        f"/api/portfolio/holdings/{holding.id}/conviction-log",
        headers=auth_headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# API: POST manual note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_manual_note(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    thesis = await _create_thesis(db, test_user, holding)
    await db.commit()

    response = await client.post(
        f"/api/portfolio/holdings/{holding.id}/conviction-log",
        json={"content": "Still confident after earnings call"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["entry_type"] == MANUAL_NOTE
    assert data["content"] == "Still confident after earnings call"
    assert data["thesis_id"] == str(thesis.id)


@pytest.mark.asyncio
async def test_post_manual_note_no_thesis(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    await db.commit()

    response = await client.post(
        f"/api/portfolio/holdings/{holding.id}/conviction-log",
        json={"content": "Note without thesis"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_manual_note_empty_content(client, db, test_user, auth_headers):
    holding = await _create_holding(db, test_user)
    await _create_thesis(db, test_user, holding)
    await db.commit()

    response = await client.post(
        f"/api/portfolio/holdings/{holding.id}/conviction-log",
        json={"content": ""},
        headers=auth_headers,
    )
    assert response.status_code == 422
