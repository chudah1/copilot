"""Real-time alerts — the timely 'we'll tell you' half of the monitoring promise.

A weekly digest is too slow for a thesis that just broke. When a thesis-breaking
signal flips a position to needs_review, email the user immediately. The transition
active/draft -> needs_review happens at most once per break, so the alert is
naturally deduped (no re-firing while the thesis stays in review).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _clean(ticker: str) -> str:
    return ticker.replace("_US_EQ", "").replace("_EQ", "")


async def maybe_send_thesis_break_alert(*, user, ticker: str, summary: str | None) -> bool:
    """Email the user that a core reason just broke. Gated by the email master
    switch; best-effort, never raises."""
    try:
        if not user or not getattr(user, "email", None):
            return False
        if (user.preferences or {}).get("email_enabled", True) is False:
            return False

        from app.services.email import send_thesis_break_email

        return await send_thesis_break_email(
            user.email,
            _clean(ticker),
            summary or "A monitoring signal contradicted a core reason for owning this position.",
        )
    except Exception:
        logger.exception("Failed to send thesis-break alert for %s", ticker)
        return False
