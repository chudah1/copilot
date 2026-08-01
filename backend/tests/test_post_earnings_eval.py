from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.jobs.post_earnings_eval import (
    event_requires_post_earnings_email,
    run_post_earnings_evaluation,
)
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password
from app.services.check_now import CheckNowResult


def _event(*, severity="warning", verdict="threatens"):
    return SimpleNamespace(severity=severity, verdict=verdict)


def test_post_earnings_email_requires_adverse_evidence():
    assert event_requires_post_earnings_email(_event()) is True
    assert event_requires_post_earnings_email(_event(severity="thesis_breaking")) is True
    assert event_requires_post_earnings_email(_event(verdict="supports")) is False
    assert event_requires_post_earnings_email(_event(verdict="neutral")) is False
    assert event_requires_post_earnings_email(_event(severity="info")) is False


@pytest.mark.parametrize(
    ("severity", "verdict", "expected_email_count"),
    [
        ("warning", "threatens", 1),
        ("info", "supports", 0),
    ],
)
@pytest.mark.asyncio
async def test_post_earnings_job_sends_one_adverse_only_email(
    db,
    job_session_factory,
    severity,
    verdict,
    expected_email_count,
):
    user = User(
        email="earnings@example.com",
        password_hash=hash_password("testpass123"),
        preferences={"email_enabled": True, "earnings_alerts": True},
    )
    db.add(user)
    await db.flush()
    holding = Holding(
        user_id=user.id,
        ticker="NOW",
        name="ServiceNow",
        quantity=1,
        average_cost_basis=100,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Enterprise workflow demand remains durable.",
        confidence="medium",
        review_cadence_days=90,
        source="user",
    )
    db.add(thesis)
    db.add(
        EarningsCalendar(
            ticker="NOW",
            report_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    await db.commit()

    async def fake_check_now(holding, thesis, session, *, send_alerts=True):
        assert send_alerts is False
        event = MonitoringEvent(
            holding_id=holding.id,
            thesis_id=thesis.id,
            event_type="earnings_call_transcript",
            severity=severity,
            title="NOW reported earnings",
            summary="New evidence",
            verdict=verdict,
        )
        session.add(event)
        await session.commit()
        return CheckNowResult(
            status="completed",
            events_created=1,
            created_event_ids=[event.id],
        )

    with patch(
        "app.jobs.post_earnings_eval.async_session",
        job_session_factory,
    ), patch(
        "app.jobs.post_earnings_eval.run_check_now",
        new_callable=AsyncMock,
        side_effect=fake_check_now,
    ), patch(
        "app.jobs.post_earnings_eval.send_earnings_alert_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as send_email:
        await run_post_earnings_evaluation()

    assert send_email.await_count == expected_email_count
