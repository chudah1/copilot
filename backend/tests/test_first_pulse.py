"""Tests for the activation first-pulse: a freshly-onboarded user must get a real
monitoring pass in their first session, not an unverified 'all calm' dashboard."""
from unittest.mock import AsyncMock, patch

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.check_now import (
    _holdings_needing_first_pulse,
    _run_first_pulse_with_session,
    run_first_pulse,
)

_CHECK_NOW = "app.services.check_now"


async def _add_holding(db, user_id, ticker="AAPL", value=1000.0):
    holding = Holding(
        user_id=user_id,
        ticker=ticker,
        name=ticker,
        quantity=10,
        average_cost_basis=100,
        current_price=100,
        current_value=value,
    )
    db.add(holding)
    await db.flush()
    return holding


async def _add_thesis(db, user_id, holding_id, status="active"):
    thesis = Thesis(
        user_id=user_id,
        holding_id=holding_id,
        status=status,
        thesis_kind="company",
        why_own_it="Strong ecosystem.",
        must_remain_true="Revenue keeps growing.",
        what_would_change_my_mind="A major revenue miss.",
        confidence="medium",
        review_cadence_days=7,
        interpretation={"watch_hints": []},
        source="ai_assisted",
    )
    db.add(thesis)
    await db.flush()
    return thesis


async def _add_event(db, holding_id, thesis_id, event_type="price_move"):
    event = MonitoringEvent(
        holding_id=holding_id,
        thesis_id=thesis_id,
        event_type=event_type,
        severity="info",
        title="t",
        summary="s",
    )
    db.add(event)
    await db.flush()
    return event


async def test_picks_holding_with_monitorable_thesis_and_no_events(db, test_user):
    holding = await _add_holding(db, test_user.id)
    await _add_thesis(db, test_user.id, holding.id)
    await db.commit()

    pairs = await _holdings_needing_first_pulse(
        db, user_id=test_user.id, holding_id=None, limit=5
    )
    assert [h.id for h, _ in pairs] == [holding.id]


async def test_skips_holding_that_already_has_a_real_event(db, test_user):
    holding = await _add_holding(db, test_user.id)
    thesis = await _add_thesis(db, test_user.id, holding.id)
    await _add_event(db, holding.id, thesis.id)  # already pulsed
    await db.commit()

    pairs = await _holdings_needing_first_pulse(
        db, user_id=test_user.id, holding_id=None, limit=5
    )
    assert pairs == []


async def test_inactive_only_events_do_not_count_as_pulsed(db, test_user):
    # A holding whose only event is monitoring_inactive has never really been
    # checked — it should still get its first pulse once it has a live thesis.
    holding = await _add_holding(db, test_user.id)
    thesis = await _add_thesis(db, test_user.id, holding.id)
    await _add_event(db, holding.id, thesis.id, event_type="monitoring_inactive")
    await db.commit()

    pairs = await _holdings_needing_first_pulse(
        db, user_id=test_user.id, holding_id=None, limit=5
    )
    assert [h.id for h, _ in pairs] == [holding.id]


async def test_skips_holding_with_no_thesis(db, test_user):
    await _add_holding(db, test_user.id)  # no thesis attached
    await db.commit()

    pairs = await _holdings_needing_first_pulse(
        db, user_id=test_user.id, holding_id=None, limit=5
    )
    assert pairs == []


async def test_holding_id_filter_restricts_to_one(db, test_user):
    h1 = await _add_holding(db, test_user.id, ticker="AAPL")
    h2 = await _add_holding(db, test_user.id, ticker="MSFT")
    await _add_thesis(db, test_user.id, h1.id)
    await _add_thesis(db, test_user.id, h2.id)
    await db.commit()

    pairs = await _holdings_needing_first_pulse(
        db, user_id=test_user.id, holding_id=h2.id, limit=5
    )
    assert [h.id for h, _ in pairs] == [h2.id]


async def test_run_with_session_checks_each_and_counts(db, test_user):
    h1 = await _add_holding(db, test_user.id, ticker="AAPL", value=2000)
    h2 = await _add_holding(db, test_user.id, ticker="MSFT", value=1000)
    await _add_thesis(db, test_user.id, h1.id)
    await _add_thesis(db, test_user.id, h2.id)
    await db.commit()

    with patch(f"{_CHECK_NOW}.run_check_now", new_callable=AsyncMock) as m_check:
        checked = await _run_first_pulse_with_session(
            db, user_id=test_user.id, holding_id=None, limit=5
        )

    assert checked == 2
    assert m_check.await_count == 2
    # Biggest position first.
    first_holding = m_check.await_args_list[0].args[0]
    assert first_holding.ticker == "AAPL"


async def test_one_failure_does_not_stop_the_rest(db, test_user):
    h1 = await _add_holding(db, test_user.id, ticker="AAPL", value=2000)
    h2 = await _add_holding(db, test_user.id, ticker="MSFT", value=1000)
    await _add_thesis(db, test_user.id, h1.id)
    await _add_thesis(db, test_user.id, h2.id)
    await db.commit()

    async def _flaky(holding, thesis, db):
        if holding.ticker == "AAPL":
            raise RuntimeError("market data outage")

    with patch(f"{_CHECK_NOW}.run_check_now", side_effect=_flaky):
        checked = await _run_first_pulse_with_session(
            db, user_id=test_user.id, holding_id=None, limit=5
        )

    assert checked == 1  # MSFT still got checked


async def test_run_first_pulse_respects_kill_switch(db, test_user):
    holding = await _add_holding(db, test_user.id)
    await _add_thesis(db, test_user.id, holding.id)
    await db.commit()

    with patch(f"{_CHECK_NOW}.settings.enable_first_pulse", False), patch(
        "app.database.async_session"
    ) as m_session:
        await run_first_pulse(test_user.id)

    m_session.assert_not_called()  # short-circuits before opening a session


async def test_run_first_pulse_never_raises_on_session_failure(test_user):
    # The background task must swallow everything — a DB hiccup can't crash it.
    with patch(f"{_CHECK_NOW}.settings.enable_first_pulse", True), patch(
        "app.database.async_session", side_effect=RuntimeError("db down")
    ):
        await run_first_pulse(test_user.id)  # must not raise
