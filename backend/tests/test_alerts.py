"""Tests for the real-time thesis-break alert gating."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.alerts import (
    maybe_send_thesis_break_alert,
    prepare_monitoring_alert,
    send_monitoring_alert,
)

_EMAIL = "app.services.email.send_thesis_break_email"


def _user(email="u@example.com", email_enabled=True):
    return SimpleNamespace(email=email, preferences={"email_enabled": email_enabled})


async def test_sends_when_enabled_and_cleans_ticker():
    with patch(_EMAIL, new_callable=AsyncMock, return_value=True) as m:
        ok = await maybe_send_thesis_break_alert(user=_user(), ticker="NVDA_US_EQ", summary="Margins compressed.")
    assert ok is True
    m.assert_awaited_once()
    assert m.await_args.args[1] == "NVDA"          # broker suffix stripped
    assert m.await_args.args[2] == "Margins compressed."


async def test_skips_when_email_disabled():
    with patch(_EMAIL, new_callable=AsyncMock) as m:
        ok = await maybe_send_thesis_break_alert(user=_user(email_enabled=False), ticker="X", summary="s")
    assert ok is False
    m.assert_not_awaited()


async def test_skips_when_no_email():
    ok = await maybe_send_thesis_break_alert(
        user=SimpleNamespace(email=None, preferences={}), ticker="X", summary="s"
    )
    assert ok is False


async def test_fallback_summary_when_none():
    with patch(_EMAIL, new_callable=AsyncMock, return_value=True) as m:
        await maybe_send_thesis_break_alert(user=_user(), ticker="X", summary=None)
    assert "contradicted a core reason" in m.await_args.args[2]


async def test_never_raises_on_send_failure():
    with patch(_EMAIL, new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        ok = await maybe_send_thesis_break_alert(user=_user(), ticker="X", summary="s")
    assert ok is False


def _event(*, severity="warning", verdict="threatens"):
    return SimpleNamespace(
        severity=severity,
        verdict=verdict,
        ai_analysis="Revenue growth weakened.",
        evidence_summary=None,
        summary="Revenue update.",
    )


def test_prepares_warning_when_user_wants_warning_alerts():
    alert = prepare_monitoring_alert(
        email="u@example.com",
        preferences={"email_enabled": True, "notification_sensitivity": "all"},
        ticker="NOW_US_EQ",
        status_before="active",
        persisted_events=[_event()],
    )

    assert alert is not None
    assert alert.severity == "warning"
    assert alert.ticker == "NOW"


def test_skips_warning_for_thesis_breaking_only_sensitivity():
    alert = prepare_monitoring_alert(
        email="u@example.com",
        preferences={
            "email_enabled": True,
            "notification_sensitivity": "thesis_breaking_only",
        },
        ticker="NOW",
        status_before="active",
        persisted_events=[_event()],
    )

    assert alert is None


def test_skips_supporting_warning_and_position_already_in_review():
    assert prepare_monitoring_alert(
        email="u@example.com",
        preferences={"email_enabled": True, "notification_sensitivity": "all"},
        ticker="NOW",
        status_before="active",
        persisted_events=[_event(verdict="supports")],
    ) is None
    assert prepare_monitoring_alert(
        email="u@example.com",
        preferences={"email_enabled": True, "notification_sensitivity": "all"},
        ticker="NOW",
        status_before="needs_review",
        persisted_events=[_event(severity="thesis_breaking")],
    ) is None


async def test_dispatches_warning_template():
    alert = prepare_monitoring_alert(
        email="u@example.com",
        preferences={"email_enabled": True, "notification_sensitivity": "all"},
        ticker="NOW",
        status_before="active",
        persisted_events=[_event()],
    )
    assert alert is not None

    with patch(
        "app.services.email.send_thesis_warning_email",
        new_callable=AsyncMock,
        return_value=True,
    ) as send_warning:
        assert await send_monitoring_alert(alert) is True

    send_warning.assert_awaited_once_with(
        "u@example.com",
        "NOW",
        "Revenue growth weakened.",
    )
