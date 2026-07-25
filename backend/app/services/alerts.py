"""Immediate monitoring alerts.

The monitoring pipelines persist evidence first, commit it, then dispatch one
best-effort email for the strongest newly persisted item. Warning emails follow
the user's sensitivity setting; thesis-breaking emails always qualify while
email is enabled.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitoringAlert:
    to_email: str
    ticker: str
    severity: str
    summary: str


def _clean(ticker: str) -> str:
    return ticker.replace("_US_EQ", "").replace("_EQ", "")


def prepare_monitoring_alert(
    *,
    email: str | None,
    preferences: dict | None,
    ticker: str,
    status_before: str,
    persisted_events: Iterable,
) -> MonitoringAlert | None:
    """Select one alert from events that were actually committed by this pass.

    A position already awaiting a decision does not fire another immediate
    alert. That transition is the dedupe boundary; new evidence still remains
    available in the app and digest.
    """
    if not email or (preferences or {}).get("email_enabled", True) is False:
        return None
    if status_before not in {"active", "draft"}:
        return None

    sensitivity = (preferences or {}).get("notification_sensitivity", "all")
    candidates = []
    for event in persisted_events:
        severity = getattr(event, "severity", None)
        verdict = getattr(event, "verdict", None)
        if verdict in {"supports", "neutral"}:
            continue
        if severity == "thesis_breaking":
            priority = 0
        elif severity == "warning" and sensitivity == "all":
            priority = 1
        else:
            continue
        candidates.append((priority, event))

    if not candidates:
        return None

    _, event = min(candidates, key=lambda item: item[0])
    summary = next(
        (
            value.strip()
            for value in (
                getattr(event, "ai_analysis", None),
                getattr(event, "evidence_summary", None),
                getattr(event, "summary", None),
            )
            if isinstance(value, str) and value.strip()
        ),
        "New evidence is testing a reason you wrote for owning this position.",
    )
    return MonitoringAlert(
        to_email=email,
        ticker=_clean(ticker),
        severity=event.severity,
        summary=summary,
    )


async def send_monitoring_alert(alert: MonitoringAlert) -> bool:
    """Dispatch a prepared alert after the evidence transaction commits."""
    try:
        if alert.severity == "thesis_breaking":
            from app.services.email import send_thesis_break_email

            return await send_thesis_break_email(
                alert.to_email,
                alert.ticker,
                alert.summary,
            )

        from app.services.email import send_thesis_warning_email

        return await send_thesis_warning_email(
            alert.to_email,
            alert.ticker,
            alert.summary,
        )
    except Exception:
        logger.exception("Failed to send monitoring alert for %s", alert.ticker)
        return False


async def maybe_send_thesis_break_alert(*, user, ticker: str, summary: str | None) -> bool:
    """Backward-compatible direct thesis-break sender."""
    if not user:
        return False
    alert = MonitoringAlert(
        to_email=getattr(user, "email", "") or "",
        ticker=_clean(ticker),
        severity="thesis_breaking",
        summary=summary or "A monitoring signal contradicted a core reason for owning this position.",
    )
    if not alert.to_email or (getattr(user, "preferences", None) or {}).get("email_enabled", True) is False:
        return False
    return await send_monitoring_alert(alert)
