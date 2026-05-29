"""Conviction log: append-only record of every thesis-related interaction."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conviction_log_entry import ConvictionLogEntry

# Entry type constants
REASON_CREATED = "reason_created"
SIGNALS_GENERATED = "signals_generated"
SIGNAL_CONFIRMED = "signal_confirmed"
SIGNAL_REMOVED = "signal_removed"
EVIDENCE_RECEIVED = "evidence_received"
EVIDENCE_REVIEWED = "evidence_reviewed"
REASON_UPDATED = "reason_updated"
REASON_INVALIDATED = "reason_invalidated"
POST_EARNINGS_REVIEW = "post_earnings_review"
QUARTERLY_REVIEW = "quarterly_review"
MANUAL_NOTE = "manual_note"
FLOOR_APPLIED = "floor_applied"


def append_log_entry(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
    holding_id: uuid.UUID,
    user_id: uuid.UUID,
    entry_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    claim_id: uuid.UUID | None = None,
    signal_id: uuid.UUID | None = None,
) -> ConvictionLogEntry:
    """Append an entry to the conviction log. Caller is responsible for commit."""
    entry = ConvictionLogEntry(
        thesis_id=thesis_id,
        holding_id=holding_id,
        user_id=user_id,
        entry_type=entry_type,
        content=content,
        metadata_json=metadata,
        claim_id=claim_id,
        signal_id=signal_id,
    )
    db.add(entry)
    return entry
