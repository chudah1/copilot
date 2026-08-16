import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis


@pytest.mark.asyncio
async def test_dashboard_workspace_prioritizes_live_review_over_missing_case(
    client, auth_headers, db, test_user
):
    review_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=5,
        average_cost_basis=120,
        current_value=900,
        currency="USD",
    )
    missing_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="AAPL",
        name="Apple",
        quantity=10,
        average_cost_basis=150,
        current_value=1600,
        currency="USD",
    )
    db.add_all([review_holding, missing_holding])
    await db.flush()

    thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=review_holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="AI infrastructure demand stays strong.",
        must_remain_true="GPU demand remains strong.",
        what_would_change_my_mind="Data-center demand weakens materially.",
        confidence="high",
        review_cadence_days=14,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    event = MonitoringEvent(
        id=uuid.uuid4(),
        holding_id=review_holding.id,
        thesis_id=thesis.id,
        event_type="news_or_earnings_candidate",
        severity="thesis_breaking",
        title="GPU demand weakens",
        summary="Orders slowed materially this quarter.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    response = await client.get("/api/dashboard/workspace", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["portfolio_state"]["kind"] == "needs_decision"
    assert data["summary_metrics"]["needs_decision_count"] == 1
    assert data["summary_metrics"]["needs_written_case_count"] == 1
    assert data["top_decision"]["holding"]["ticker"] == "NVDA"
    assert data["top_decision"]["decision_state"] == "needs_decision"
    assert data["blind_spots"][0]["holding"]["ticker"] == "AAPL"
    assert data["blind_spots"][0]["blind_spot_kind"] == "missing"


@pytest.mark.asyncio
async def test_dashboard_workspace_surfaces_weak_and_overdue_blind_spots(
    client, auth_headers, db, test_user
):
    weak_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="SHOP",
        name="Shopify",
        quantity=8,
        average_cost_basis=80,
        current_value=1000,
        currency="USD",
    )
    overdue_holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="MSFT",
        name="Microsoft",
        quantity=6,
        average_cost_basis=200,
        current_value=1200,
        currency="USD",
    )
    db.add_all([weak_holding, overdue_holding])
    await db.flush()

    db.add(
        Thesis(
            id=uuid.uuid4(),
            user_id=test_user.id,
            holding_id=weak_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Growth.",
            confidence="medium",
            review_cadence_days=30,
            interpretation={"monitorability": "low", "ambiguity_note": "Too vague to monitor."},
            source="user",
        )
    )
    db.add(
        Thesis(
            id=uuid.uuid4(),
            user_id=test_user.id,
            holding_id=overdue_holding.id,
            status="active",
            thesis_kind="company",
            why_own_it="Cloud + AI compounding.",
            must_remain_true="Cloud demand stays strong.",
            what_would_change_my_mind="Growth stalls.",
            confidence="high",
            review_cadence_days=14,
            updated_at=datetime.now(timezone.utc) - timedelta(days=120),
            interpretation={"monitorability": "high"},
            source="user",
        )
    )
    await db.commit()

    response = await client.get("/api/dashboard/workspace", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    kinds = {item["blind_spot_kind"] for item in data["blind_spots"]}
    assert "weak" in kinds
    assert "review_overdue" in kinds


@pytest.mark.asyncio
async def test_dashboard_workspace_includes_recent_decisions(
    client, auth_headers, db, test_user
):
    holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="AMD",
        name="AMD",
        quantity=10,
        average_cost_basis=90,
        current_value=950,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Data-center share gains continue.",
        must_remain_true="Server momentum holds.",
        what_would_change_my_mind="Share gains reverse.",
        confidence="medium",
        review_cadence_days=30,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    db.add(
        ConvictionLogEntry(
            id=uuid.uuid4(),
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=test_user.id,
            entry_type="evidence_reviewed",
            content="reaffirmed: Server share gains still look intact.",
            metadata_json={"action": "reaffirmed", "assumption_label": "Server share gains"},
        )
    )
    await db.commit()

    response = await client.get("/api/dashboard/workspace", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert len(data["recent_decisions"]) == 1
    assert data["recent_decisions"][0]["ticker"] == "AMD"
    assert data["recent_decisions"][0]["action"] == "reaffirmed"
    assert data["recent_decisions"][0]["assumption_label"] == "Server share gains"


@pytest.mark.asyncio
async def test_dashboard_workspace_includes_decision_memory(
    client, auth_headers, db, test_user
):
    holding = Holding(
        id=uuid.uuid4(),
        user_id=test_user.id,
        ticker="META",
        name="Meta",
        quantity=7,
        average_cost_basis=300,
        current_value=2500,
        currency="USD",
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        id=uuid.uuid4(),
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Ads and AI monetization continue compounding.",
        must_remain_true="Ad demand and margins stay resilient.",
        what_would_change_my_mind="Engagement or margins break down.",
        confidence="medium",
        review_cadence_days=30,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    resolved_snapshot = DecisionSnapshot(
        id=uuid.uuid4(),
        user_id=test_user.id,
        thesis_id=thesis.id,
        holding_id=holding.id,
        verdict="reaffirmed",
        bucket="held",
        decision_source="event_review",
        bet_text="Ad demand still looks resilient.",
        condition_snapshot={"watch_hints": [{"kind": "metric_threshold"}]},
        decided_at=datetime.now(timezone.utc) - timedelta(days=30),
        resolved_at=datetime.now(timezone.utc) - timedelta(days=2),
        resolution_json={
            "read": "You held META through a warning. The conditions you were watching still hold.",
            "conditions": [{"held": True}],
        },
    )
    open_snapshot = DecisionSnapshot(
        id=uuid.uuid4(),
        user_id=test_user.id,
        thesis_id=thesis.id,
        holding_id=holding.id,
        verdict="reaffirmed",
        bucket="held",
        decision_source="event_review",
        bet_text="AI monetization still looks early.",
        condition_snapshot={"watch_hints": [{"kind": "metric_threshold"}]},
        decided_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    db.add_all([resolved_snapshot, open_snapshot])
    await db.commit()

    response = await client.get("/api/dashboard/workspace", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["decision_memory"]["resolved_count"] == 1
    assert data["decision_memory"]["open_followups_count"] == 1
    assert data["decision_memory"]["has_pattern"] is False
    assert data["decision_memory"]["primary_pattern"] is None
