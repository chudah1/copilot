from datetime import datetime, timezone

import pytest

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.onboarding_draft import OnboardingDraft
from app.models.thesis import Thesis
from app.services.dashboard_command_center import build_dashboard_command_center


@pytest.mark.asyncio
async def test_command_center_groups_review_draft_and_supporting(db, test_user):
    review_holding = Holding(
        user_id=test_user.id,
        ticker="NVDA",
        name="NVIDIA",
        quantity=2,
        average_cost_basis=100,
        current_price=120,
        current_value=240,
    )
    draft_holding = Holding(
        user_id=test_user.id,
        ticker="AMD",
        name="AMD",
        quantity=2,
        average_cost_basis=100,
        current_price=110,
        current_value=220,
    )
    support_holding = Holding(
        user_id=test_user.id,
        ticker="MSFT",
        name="Microsoft",
        quantity=2,
        average_cost_basis=100,
        current_price=130,
        current_value=260,
    )
    db.add_all([review_holding, draft_holding, support_holding])
    await db.flush()

    review_thesis = Thesis(
        user_id=test_user.id,
        holding_id=review_holding.id,
        status="needs_review",
        thesis_kind="company",
        why_own_it="AI demand stays strong.",
        must_remain_true="Growth stays strong.",
        what_would_change_my_mind="Demand weakens.",
        confidence="high",
        review_cadence_days=30,
        interpretation={"monitorability": "high"},
        source="user",
    )
    draft_thesis = Thesis(
        user_id=test_user.id,
        holding_id=draft_holding.id,
        status="draft",
        thesis_kind="company",
        why_own_it="PC recovery helps the setup.",
        must_remain_true="Margins improve.",
        what_would_change_my_mind="Recovery stalls.",
        confidence="medium",
        review_cadence_days=30,
        interpretation={"monitorability": "medium"},
        source="ai_draft",
    )
    support_thesis = Thesis(
        user_id=test_user.id,
        holding_id=support_holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Cloud demand holds up.",
        must_remain_true="Azure keeps compounding.",
        what_would_change_my_mind="Cloud slows materially.",
        confidence="high",
        review_cadence_days=30,
        interpretation={"monitorability": "high"},
        source="user",
    )
    db.add_all([review_thesis, draft_thesis, support_thesis])
    await db.flush()

    db.add(
        OnboardingDraft(
            user_id=test_user.id,
            holding_id=draft_holding.id,
            thesis_id=draft_thesis.id,
            status="ready",
        )
    )
    db.add(
        MonitoringEvent(
            holding_id=support_holding.id,
            thesis_id=support_thesis.id,
            event_type="earnings_call_transcript",
            severity="info",
            title="MSFT: earnings call transcript",
            summary="Azure demand remained strong.",
            ai_analysis="Azure demand remained strong.",
            raw_data={"evidence": {}},
            evidence_type="earnings_call_transcript",
            verdict="supports",
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()

    center = await build_dashboard_command_center(db, user=test_user)
    sections = {section.kind: section for section in center.sections}

    assert any(item.holding.ticker == "NVDA" for item in sections["needs_review"].items)
    assert any(item.holding.ticker == "AMD" and item.workflow_state == "draft_ready" for item in sections["unclear_theses"].items)
    assert any(item.holding.ticker == "MSFT" for item in sections["held_up"].items)
