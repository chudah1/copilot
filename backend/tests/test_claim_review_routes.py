from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis


async def _seed(db, test_user):
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
        confidence="high",
        review_cadence_days=30,
        source="user",
    )
    db.add(thesis)
    await db.flush()
    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="gemini_news",
        severity="thesis_breaking",
        title="Ban announced",
        summary="A stated break condition occurred.",
        verdict="threatens",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()
    return holding, thesis, event


@pytest.mark.asyncio
async def test_check_in_returns_general_bucket_needing_review(client, db, test_user, auth_headers):
    _holding, thesis, _event = await _seed(db, test_user)

    response = await client.get(f"/api/theses/{thesis.id}/check-in", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["needs_review_count"] == 1
    general = body["claims"][0]
    assert general["claim_id"] is None
    assert general["needs_review"] is True
    assert len(general["threatens"]) == 1


@pytest.mark.asyncio
async def test_submit_claim_reviews_roundtrip(client, db, test_user, auth_headers):
    holding, thesis, _event = await _seed(db, test_user)

    response = await client.post(
        f"/api/theses/{thesis.id}/claim-reviews",
        headers=auth_headers,
        json={"decisions": [{"claim_id": None, "status": "holds", "notes": "Still fine"}]},
    )

    assert response.status_code == 200
    assert response.json()["thesis_status"] == "active"

    check_in = await client.get(f"/api/theses/{thesis.id}/check-in", headers=auth_headers)
    general = check_in.json()["claims"][0]
    assert general["status"] == "holds"
    assert general["needs_review"] is False
    assert general["threatens"] == []

    events = await client.get(
        f"/api/monitoring/holdings/{holding.id}/events",
        headers=auth_headers,
    )
    assert events.json()[0]["review_action"] == "reaffirmed"

    pulse = await client.get("/api/portfolio/pulse", headers=auth_headers)
    position = pulse.json()["pulses"][0]
    assert position["pulse_status"] == "intact"
    assert position["unresolved_event_count"] == 0


@pytest.mark.asyncio
async def test_submit_broken_without_thesis_action_is_400(client, db, test_user, auth_headers):
    _holding, thesis, _event = await _seed(db, test_user)

    response = await client.post(
        f"/api/theses/{thesis.id}/claim-reviews",
        headers=auth_headers,
        json={"decisions": [{"claim_id": None, "status": "broken"}]},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_event_review_endpoint_only_accepts_flagging(client, db, test_user, auth_headers):
    _holding, _thesis, event = await _seed(db, test_user)

    rejected = await client.post(
        f"/api/monitoring/events/{event.id}/review",
        headers=auth_headers,
        json={"action": "reaffirmed"},
    )
    assert rejected.status_code == 400

    flagged = await client.post(
        f"/api/monitoring/events/{event.id}/review",
        headers=auth_headers,
        json={"action": "not_relevant"},
    )
    assert flagged.status_code == 200
