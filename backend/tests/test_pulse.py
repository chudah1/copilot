import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coverage_pass import CoveragePass
from app.models.claim_review import ClaimReview
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_review import ThesisReview


@pytest.mark.asyncio
async def test_pulse_no_holdings(client, auth_headers):
    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pulses"] == []
    assert data["next_digest_at"] is not None


@pytest.mark.asyncio
async def test_pulse_holding_without_thesis(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "review"
    assert pulses[0]["has_thesis"] is False
    assert pulses[0]["urgency_score"] == 100


@pytest.mark.asyncio
async def test_pulse_intact_thesis_no_events(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "intact"
    assert pulses[0]["has_thesis"] is True


@pytest.mark.asyncio
async def test_pulse_last_checked_reflects_monitored_at_without_events(
    client, auth_headers, test_user, db: AsyncSession
):
    # A quiet first pulse creates no event but stamps last_monitored_at — the
    # dashboard must still be able to say "checked X ago", not leave it blank.
    checked_at = datetime.now(timezone.utc) - timedelta(hours=2)
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id, last_monitored_at=checked_at,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "intact"
    assert pulses[0]["last_checked_at"] is not None


@pytest.mark.asyncio
async def test_pulse_review_on_breaking_event(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AAPL", name="Apple Inc",
        quantity=10, average_cost_basis=150, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Growth play", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="metric_threshold", severity="thesis_breaking",
        title="Revenue declined", summary="Revenue growth turned negative.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "review"


@pytest.mark.asyncio
async def test_pulse_watch_on_warning_event(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="MSFT", name="Microsoft",
        quantity=5, average_cost_basis=300, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Cloud dominance", confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="news_or_earnings_candidate", severity="warning",
        title="Azure growth slowing", summary="Azure growth decelerated to 22%.",
        ai_analysis="Azure growth is being tested after the slowdown. Review whether the cloud thesis still holds.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulses = resp.json()["pulses"]
    assert len(pulses) == 1
    assert pulses[0]["pulse_status"] == "watch"
    assert pulses[0]["pulse_basis"] == "evidence"
    assert pulses[0]["assumption_label"] == "Azure growth slowing"
    assert pulses[0]["latest_event_summary"] == "Azure growth is being tested after the slowdown. Review whether the cloud thesis still holds."
    assert pulses[0]["latest_event_at"] is not None
    assert pulses[0]["urgency_score"] > 55


@pytest.mark.asyncio
async def test_pulse_only_counts_evidence_that_needs_a_decision(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="NOW", name="ServiceNow",
        quantity=2, average_cost_basis=600, currency="GBP",
        user_id=test_user.id,
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Subscription growth", confidence="medium",
    )
    db.add_all([holding, thesis])
    await db.commit()

    now = datetime.now(timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="supports",
            title="Growth held up", summary="Subscription growth remained solid.",
            created_at=now,
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="info", verdict="neutral",
            title="Background", summary="No direct bearing on the case.",
            created_at=now - timedelta(minutes=1),
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Growth slowed", summary="Subscription growth decelerated.",
            created_at=now - timedelta(minutes=2),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "watch"
    # One warning is early pressure, not yet a claim decision.
    assert pulse["unresolved_event_count"] == 0
    assert pulse["latest_event_summary"] == "Subscription growth decelerated."


@pytest.mark.asyncio
async def test_pulse_does_not_resurface_events_cleared_by_claim_review(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="NOW", name="ServiceNow",
        quantity=2, average_cost_basis=600, currency="GBP",
        user_id=test_user.id,
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Subscription growth", confidence="medium",
    )
    db.add_all([holding, thesis])
    await db.commit()

    now = datetime.now(timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Growth slowed", summary="Subscription growth decelerated.",
            created_at=now - timedelta(days=2),
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Backlog slowed", summary="Remaining obligations decelerated.",
            created_at=now - timedelta(days=2),
        ),
        ClaimReview(
            thesis_id=thesis.id,
            claim_id=None,
            session_id=uuid.uuid4(),
            status="holds",
            created_at=now - timedelta(days=1),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "intact"
    assert pulse["pulse_basis"] == "none"
    assert pulse["unresolved_event_count"] == 0


@pytest.mark.asyncio
async def test_pulse_counts_pending_claims_not_individual_events(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="NOW", name="ServiceNow",
        quantity=2, average_cost_basis=600, currency="GBP",
        user_id=test_user.id,
    )
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Subscription growth", confidence="medium",
    )
    db.add_all([holding, thesis])
    await db.commit()

    now = datetime.now(timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Growth slowed", summary="Subscription growth decelerated.",
            created_at=now,
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="news", severity="warning", verdict="threatens",
            title="Backlog slowed", summary="Remaining obligations decelerated.",
            created_at=now - timedelta(minutes=1),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "review"
    assert pulse["pulse_basis"] == "evidence"
    assert pulse["unresolved_event_count"] == 1


@pytest.mark.asyncio
async def test_pulse_keeps_old_unresolved_evidence_in_the_decision_inbox(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="AMD", name="AMD",
        quantity=5, average_cost_basis=100, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI infrastructure share gains", confidence="medium",
    )
    db.add(thesis)
    await db.commit()
    db.add(MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="price_move", severity="warning",
        title="Price moved", summary="Price moved sharply.",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    ))
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "watch"
    assert pulse["pulse_basis"] == "evidence"
    assert pulse["recent_event_count"] == 0
    assert pulse["unresolved_event_count"] == 0


@pytest.mark.asyncio
async def test_pulse_ignores_unresolved_evidence_from_an_invalidated_case(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="AMD", name="AMD",
        quantity=5, average_cost_basis=100, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    old_thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="invalidated", why_own_it="PC demand recovers", confidence="medium",
        created_at=datetime.now(timezone.utc) - timedelta(days=60),
    )
    active_thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI accelerator share gains", confidence="medium",
        created_at=datetime.now(timezone.utc),
    )
    db.add_all([old_thesis, active_thesis])
    await db.commit()

    db.add(MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=old_thesis.id,
        event_type="news_or_earnings_candidate", severity="thesis_breaking",
        title="PC demand weakened", summary="The old written case broke.",
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
    ))
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "intact"
    assert pulse["pulse_basis"] == "none"
    assert pulse["recent_event_count"] == 0
    assert pulse["unresolved_event_count"] == 0


@pytest.mark.asyncio
async def test_pulse_does_not_keep_reviewed_evidence_on_watch(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="MSFT", name="Microsoft",
        quantity=5, average_cost_basis=300, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()
    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Cloud demand", confidence="medium",
    )
    db.add(thesis)
    await db.commit()
    reviewed_event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="news", severity="warning",
        title="Cloud growth slowed", summary="Growth slowed.",
        created_at=datetime.now(timezone.utc),
    )
    db.add(reviewed_event)
    await db.flush()
    db.add(ThesisReview(
        id=uuid.uuid4(), thesis_id=thesis.id,
        monitoring_event_id=reviewed_event.id,
        action="not_relevant",
    ))
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "intact"
    assert pulse["recent_event_count"] == 0
    assert pulse["unresolved_event_count"] == 0


@pytest.mark.asyncio
async def test_pulse_normalizes_raw_assumption_labels(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="NVDA", name="NVIDIA",
        quantity=5, average_cost_basis=120, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI infrastructure leadership", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    event = MonitoringEvent(
        id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
        event_type="news_or_earnings_candidate", severity="warning",
        title="NVDA: news touches 'NVDA dominates GPU compute for AI training with strong demand'",
        summary="News keeps the AI demand case in focus.",
        raw_data={
            "signal_label": "NVDA:NVDA:news touches 'NVDA dominates GPU compute for AI training with strong demand'",
        },
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "watch"
    assert pulse["assumption_label"] == "dominates GPU compute for AI training with strong demand"


@pytest.mark.asyncio
async def test_pulse_batches_same_day_events_into_one_summary(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="NVDA", name="NVIDIA",
        quantity=4, average_cost_basis=800, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI infrastructure demand", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    now = datetime.now(timezone.utc)
    db.add_all([
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="earnings_surprise", severity="warning",
            title="Earnings beat", summary="Revenue beat expectations.",
            evidence_type="earnings_surprise",
            created_at=now,
        ),
        MonitoringEvent(
            id=uuid.uuid4(), holding_id=holding.id, thesis_id=thesis.id,
            event_type="earnings_call_transcript", severity="warning",
            title="Transcript review", summary="Management highlighted supply constraints.",
            evidence_type="earnings_call_transcript",
            created_at=now - timedelta(hours=1),
        ),
    ])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["recent_event_count"] == 2
    assert pulse["latest_event_summary"].startswith("2 new signals today:")


@pytest.mark.asyncio
async def test_pulse_respects_zero_current_value_for_pnl(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="XYZ", name="Example Co",
        quantity=10, average_cost_basis=100, current_value=0, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Turnaround bet", confidence="medium",
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pnl_pct"] == -100.0


@pytest.mark.asyncio
async def test_pulse_stale_thesis_uses_review_cadence_for_watch_status(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="SHOP", name="Shopify",
        quantity=3, average_cost_basis=70, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Commerce platform compounding", confidence="medium",
        review_cadence_days=30,
        updated_at=datetime.now(timezone.utc) - timedelta(days=52),
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "watch"
    assert pulse["pulse_basis"] == "case_review"
    assert pulse["reason"] == "This thesis is 52 days old and 22 days past its review cadence."
    assert pulse["urgency_score"] > 55


@pytest.mark.asyncio
async def test_pulse_stale_high_confidence_thesis_can_escalate_to_review(client, auth_headers, test_user, db: AsyncSession):
    holding = Holding(
        id=uuid.uuid4(), ticker="TSM", name="TSMC",
        quantity=6, average_cost_basis=90, currency="GBP",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Foundry leadership", confidence="high",
        review_cadence_days=30,
        updated_at=datetime.now(timezone.utc) - timedelta(days=108),
    )
    db.add(thesis)
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    assert resp.status_code == 200
    pulse = resp.json()["pulses"][0]
    assert pulse["pulse_status"] == "review"
    assert pulse["pulse_basis"] == "case_review"
    assert pulse["reason"] == "This thesis is 108 days old and far past its 30-day review cadence."
    assert pulse["urgency_score"] >= 90


@pytest.mark.asyncio
async def test_pulse_counts_sources_from_latest_coverage_pass(
    client, auth_headers, test_user, db: AsyncSession
):
    # Passive receipt: the pulse response reports how many pipeline sources
    # were queried on the latest pass. A source that was queried counts, even
    # if it returned zero candidates — "we looked" is the honest signal.
    holding = Holding(
        id=uuid.uuid4(), ticker="NVDA", name="NVIDIA",
        quantity=10, average_cost_basis=180, currency="USD",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="AI infra leader", confidence="high",
    )
    db.add(thesis)
    await db.commit()

    now = datetime.now(timezone.utc)
    older = CoveragePass(
        id=uuid.uuid4(), thesis_id=thesis.id, holding_id=holding.id,
        run_id="check_now:old", triggered_by="check_now",
        started_at=now - timedelta(hours=6),
        finished_at=now - timedelta(hours=6),
        payload={"sources": {
            "qualitative_market_data": {"queried": True, "candidates_returned": 1},
        }},
    )
    latest = CoveragePass(
        id=uuid.uuid4(), thesis_id=thesis.id, holding_id=holding.id,
        run_id="check_now:latest", triggered_by="check_now",
        started_at=now,
        finished_at=now,
        payload={"sources": {
            "qualitative_market_data": {"queried": True, "candidates_returned": 0},
            "edgar_8k": {"queried": True, "candidates_returned": 2},
            "edgar_form4": {"queried": True, "candidates_returned": 0},
            "gemini_news": {"queried": True, "candidates_returned": 0, "error": "credit exhausted"},
            "earnings_call_transcripts": {"queried": False, "candidates_returned": 0},
        }},
    )
    db.add_all([older, latest])
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    # 4 sources actually queried (qual/edgar_8k/edgar_form4/gemini_news);
    # earnings_call_transcripts was skipped so it doesn't count.
    assert pulse["sources_count"] == 4


@pytest.mark.asyncio
async def test_pulse_sources_count_stays_scoped_to_active_thesis(
    client, auth_headers, test_user, db: AsyncSession
):
    holding = Holding(
        id=uuid.uuid4(), ticker="MSFT", name="Microsoft",
        quantity=8, average_cost_basis=300, currency="USD",
        user_id=test_user.id,
    )
    db.add(holding)
    await db.commit()

    active_thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="active", why_own_it="Cloud and AI demand", confidence="high",
    )
    old_thesis = Thesis(
        id=uuid.uuid4(), holding_id=holding.id, user_id=test_user.id,
        status="invalidated", why_own_it="Legacy thesis", confidence="medium",
    )
    db.add_all([active_thesis, old_thesis])
    await db.commit()

    db.add(
        CoveragePass(
            id=uuid.uuid4(), thesis_id=old_thesis.id, holding_id=holding.id,
            run_id="check_now:old-thesis", triggered_by="check_now",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            payload={"sources": {
                "qualitative_market_data": {"queried": True, "candidates_returned": 1},
                "gemini_news": {"queried": True, "candidates_returned": 1},
            }},
        )
    )
    await db.commit()

    resp = await client.get("/api/portfolio/pulse", headers=auth_headers)
    pulse = resp.json()["pulses"][0]
    # The active thesis has never been monitored, so it should not inherit the
    # old thesis's passive receipt.
    assert pulse["sources_count"] is None
