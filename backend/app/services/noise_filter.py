from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_event import MonitoringEvent
from app.models.thesis_signal import ThesisSignal

logger = logging.getLogger(__name__)

EVIDENCE_DEDUP_DAYS = 7

# Cooldown hours per evidence_type (mapped from event_type before this runs)
COOLDOWN_HOURS: dict[str, int] = {
    "price_move": 24,
    "metric_breach": 24,
    "news": 48,
    "earnings": 48,
    "insider": 48,
}
DEFAULT_COOLDOWN_HOURS = 24

EVIDENCE_TYPE_MAP: dict[str, str] = {
    "price_move": "price_move",
    "metric_threshold": "metric_breach",
    "news_or_earnings_candidate": "news",
    "earnings_surprise": "earnings",
    "upcoming_earnings": "earnings",
    "earnings_call_transcript": "earnings",
    "insider_transaction": "insider",
}


def _get_evidence_source_id(evidence: dict[str, Any]) -> str | None:
    return (
        evidence.get("article_id")
        or evidence.get("transaction_id")
        or evidence.get("transcript_id")
    )


def _get_evidence_type(event_type: str) -> str:
    return EVIDENCE_TYPE_MAP.get(event_type, event_type)


async def _load_recent_evidence_ids(
    db: AsyncSession,
    holding_id: uuid.UUID,
    days: int = EVIDENCE_DEDUP_DAYS,
) -> set[str]:
    """Load evidence source IDs from recent events for this holding."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(MonitoringEvent.raw_data)
        .where(
            MonitoringEvent.holding_id == holding_id,
            MonitoringEvent.created_at >= cutoff,
        )
    )
    ids: set[str] = set()
    for (raw_data,) in result:
        if not raw_data or not isinstance(raw_data, dict):
            continue
        evidence = raw_data.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        if source_id:
            ids.add(source_id)
    return ids


def _apply_evidence_dedup(
    candidates: list[dict[str, Any]],
    existing_ids: set[str],
) -> list[dict[str, Any]]:
    """Rule 1: Skip candidates whose evidence source already exists in recent events."""
    filtered = []
    seen: set[str] = set()
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        if source_id:
            if source_id in existing_ids or source_id in seen:
                continue
            seen.add(source_id)
        filtered.append(candidate)
    return filtered


def _apply_signal_cooldown(
    candidates: list[dict[str, Any]],
    signal_map: dict[str, ThesisSignal],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Rule 2: Skip candidates whose signal fired within the cooldown window."""
    now = now or datetime.now(timezone.utc)
    filtered = []
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        signal_id = evidence.get("signal_id")
        if not signal_id:
            filtered.append(candidate)
            continue

        signal = signal_map.get(signal_id)
        if not signal or not signal.last_fired_at:
            filtered.append(candidate)
            continue

        evidence_type = _get_evidence_type(candidate.get("event_type", ""))
        cooldown_hours = COOLDOWN_HOURS.get(evidence_type, DEFAULT_COOLDOWN_HOURS)
        cooldown_end = signal.last_fired_at + timedelta(hours=cooldown_hours)

        if now < cooldown_end:
            logger.debug(
                "Signal cooldown: skipping %s for signal %s (cooldown until %s)",
                candidate.get("event_type"),
                signal_id,
                cooldown_end.isoformat(),
            )
            continue
        filtered.append(candidate)
    return filtered


def _apply_priority_suppression(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rule 3: If a thesis_breaking candidate exists, drop lower-severity candidates
    that share the same evidence source."""
    severity_order = {"thesis_breaking": 0, "warning": 1, "info": 2}
    # Sort by severity (highest first) for stable processing
    sorted_candidates = sorted(
        candidates,
        key=lambda c: severity_order.get(c.get("_severity", "warning"), 1),
    )

    # Collect evidence sources from thesis_breaking candidates
    breaking_sources: set[str] = set()
    for candidate in sorted_candidates:
        if candidate.get("_severity") == "thesis_breaking":
            evidence = candidate.get("evidence", {})
            source_id = _get_evidence_source_id(evidence)
            if source_id:
                breaking_sources.add(source_id)

    if not breaking_sources:
        return candidates

    filtered = []
    for candidate in candidates:
        if candidate.get("_severity") == "thesis_breaking":
            filtered.append(candidate)
            continue
        evidence = candidate.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        if source_id and source_id in breaking_sources:
            logger.debug(
                "Priority suppression: dropping %s (source %s covered by thesis_breaking)",
                candidate.get("event_type"),
                source_id,
            )
            continue
        filtered.append(candidate)
    return filtered


def _apply_minimum_relevance(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rule 4: Drop news candidates with no signal or claim match."""
    filtered = []
    for candidate in candidates:
        if candidate.get("event_type") == "news_or_earnings_candidate":
            evidence = candidate.get("evidence", {})
            has_signal = bool(evidence.get("signal_id"))
            has_claim = bool(evidence.get("claim_id"))
            if not has_signal and not has_claim:
                logger.debug(
                    "Minimum relevance: dropping unlinked news candidate: %s",
                    evidence.get("headline", "")[:80],
                )
                continue
        filtered.append(candidate)
    return filtered


async def filter_candidates(
    candidates: list[dict[str, Any]],
    holding_id: uuid.UUID,
    signal_map: dict[str, ThesisSignal],
    db: AsyncSession,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Apply all noise suppression rules. Call after signal matching, before event creation."""
    if not candidates:
        return candidates

    existing_ids = await _load_recent_evidence_ids(db, holding_id)

    # Rule 1: Evidence dedup
    candidates = _apply_evidence_dedup(candidates, existing_ids)

    # Rule 2: Signal cooldown
    candidates = _apply_signal_cooldown(candidates, signal_map, now)

    # Rule 3: Priority suppression (needs _severity annotation — applied by caller)
    candidates = _apply_priority_suppression(candidates)

    # Rule 4: Minimum relevance
    candidates = _apply_minimum_relevance(candidates)

    return candidates


async def record_signal_fired(
    signal_id: str | None,
    signal_map: dict[str, ThesisSignal],
    now: datetime | None = None,
) -> None:
    """Update last_fired_at on the signal after event creation.

    Mutates the signal object in the session — caller commits.
    """
    if not signal_id:
        return
    signal = signal_map.get(signal_id)
    if signal is None:
        return
    signal.last_fired_at = now or datetime.now(timezone.utc)
