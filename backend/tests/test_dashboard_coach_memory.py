import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.dashboard_coach_advice import DashboardCoachAdvice
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.dashboard_coach import (
    get_dashboard_coach_memory,
    record_dashboard_coach_feedback,
    sync_dashboard_coach_outcome_for_snapshot,
)
from app.services.decision_snapshots import capture_check_in_decision


@pytest.mark.asyncio
async def test_dashboard_coach_feedback_records_presented_skipped_and_acted(
    client, auth_headers
):
    advice_key = "close_open_loop:NFLX:claim_review"

    presented = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": advice_key,
            "mode": "close_open_loop",
            "event": "presented",
            "holding_id": str(uuid.uuid4()),
            "loop_key": "claim_review:test",
        },
    )
    assert presented.status_code == 200
    assert presented.json()["status"] == "presented"

    skipped = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": advice_key,
            "mode": "close_open_loop",
            "event": "skipped",
            "holding_id": str(uuid.uuid4()),
            "loop_key": "claim_review:test",
        },
    )
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"

    acted = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": advice_key,
            "mode": "close_open_loop",
            "event": "acted",
            "holding_id": str(uuid.uuid4()),
            "loop_key": "claim_review:test",
            "action_label": "Finish claim review",
        },
    )
    assert acted.status_code == 200
    assert acted.json()["status"] == "acted"

    memory = await client.get("/api/dashboard/coach-memory", headers=auth_headers)
    assert memory.status_code == 200
    data = memory.json()
    assert data["total_presented"] == 1
    assert data["skipped_count"] == 1
    assert data["acted_count"] == 1
    assert data["last_feedback"] == "acted"
    assert data["last_mode"] == "close_open_loop"
    assert data["mode_stats"]["close_open_loop"]["presented_count"] == 1
    assert data["mode_stats"]["close_open_loop"]["skipped_count"] == 1
    assert data["mode_stats"]["close_open_loop"]["acted_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_coach_memory_keeps_mode_stats_separate(
    client, auth_headers
):
    first = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": "pattern_under_pressure:NVDA:attention",
            "mode": "pattern_under_pressure",
            "event": "presented",
            "pattern_kind": "attention",
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": "sharpen_case:TSLA:weak",
            "mode": "sharpen_case",
            "event": "presented",
        },
    )
    assert second.status_code == 200

    skipped = await client.post(
        "/api/dashboard/coach-feedback",
        headers=auth_headers,
        json={
            "advice_key": "sharpen_case:TSLA:weak",
            "mode": "sharpen_case",
            "event": "skipped",
        },
    )
    assert skipped.status_code == 200

    memory = await client.get("/api/dashboard/coach-memory", headers=auth_headers)
    assert memory.status_code == 200
    data = memory.json()
    assert data["mode_stats"]["pattern_under_pressure"]["presented_count"] == 1
    assert data["mode_stats"]["pattern_under_pressure"]["skipped_count"] == 0
    assert data["mode_stats"]["sharpen_case"]["presented_count"] == 1
    assert data["mode_stats"]["sharpen_case"]["skipped_count"] == 1


@pytest.mark.asyncio
async def test_dashboard_coach_memory_tracks_helpful_outcomes_after_snapshot_resolution(
    db, test_user
):
    holding = Holding(
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=2,
        average_cost_basis=100,
        currency="USD",
        current_price=120,
        current_value=240,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        holding_id=holding.id,
        user_id=test_user.id,
        status="active",
        why_own_it="AI demand keeps compounding.",
        must_remain_true="Demand and pricing stay strong.",
        what_would_change_my_mind="Demand or pricing weakens materially.",
        interpretation={
            "monitorability": "medium",
            "watch_hints": [
                {
                    "kind": "metric_threshold",
                    "metric": "revenue_growth_yoy",
                    "operator": ">=",
                    "threshold": 20,
                }
            ],
        },
    )
    db.add(thesis)
    await db.flush()

    acted_at = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
    await record_dashboard_coach_feedback(
        db,
        user_id=test_user.id,
        advice_key="pattern_under_pressure:holding:nvda",
        mode="pattern_under_pressure",
        holding_id=holding.id,
        thesis_id=thesis.id,
        event="acted",
        action_label="Resolve NVDA now",
        now=acted_at,
    )

    snapshot = await capture_check_in_decision(
        db,
        thesis=thesis,
        holding=holding,
        bet_text="AI demand stays strong",
        exited=False,
        now=acted_at,
    )
    assert snapshot is not None
    await db.commit()

    linked_advice = (
        await db.execute(
            select(DashboardCoachAdvice).where(
                DashboardCoachAdvice.user_id == test_user.id,
                DashboardCoachAdvice.advice_key == "pattern_under_pressure:holding:nvda",
            )
        )
    ).scalar_one()
    assert linked_advice is not None
    assert linked_advice.decision_snapshot_id == snapshot.id

    snapshot.resolved_at = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    snapshot.resolution_json = {
        "conditions": [
            {"metric": "revenue_growth_yoy", "held": True, "operator": ">=", "threshold": 20, "value_now": 24}
        ]
    }
    await sync_dashboard_coach_outcome_for_snapshot(db, snapshot=snapshot, now=snapshot.resolved_at)
    await db.commit()

    memory = await get_dashboard_coach_memory(db, user_id=test_user.id)
    mode_stats = memory.mode_stats["pattern_under_pressure"]
    assert mode_stats.acted_count == 1
    assert mode_stats.resolved_count == 1
    assert mode_stats.helpful_count == 1
    assert mode_stats.hurt_count == 0
