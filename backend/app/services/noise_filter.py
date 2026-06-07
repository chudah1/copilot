from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_event import MonitoringEvent
from app.models.thesis_signal import ThesisSignal

logger = logging.getLogger(__name__)

EVIDENCE_DEDUP_DAYS = 7

_STATELESS_EVENT_TYPES = frozenset({
    "earnings_surprise",
    "upcoming_earnings",
    "metric_threshold",
    "monitoring_inactive",
})


def _candidate_event_date(candidate: dict[str, Any]) -> datetime | None:
    """Return the event datetime from a candidate's evidence dict, UTC-aware."""
    ev = candidate.get("evidence") or {}
    for key in ("call_date", "published_at", "transaction_date", "filing_date", "date"):
        raw = ev.get(key)
        if not raw:
            continue
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        if isinstance(raw, date):
            return datetime.combine(raw, datetime.min.time()).replace(tzinfo=timezone.utc)
        if isinstance(raw, str):
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    d = date.fromisoformat(raw)
                    return datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
    return None


def apply_thesis_floor(
    candidates: list[dict[str, Any]],
    thesis_created_at: datetime,
) -> list[dict[str, Any]]:
    """Drop event-dated candidates that predate this thesis.

    Stateless candidates (earnings_surprise, metric_threshold, etc.) reflect
    current market state rather than a discrete past event, so they are always
    kept. Everything else is filtered if its event date is before the thesis was
    created (minus one day of grace for timezone / scheduling skew).

    Prevents new users from receiving alerts about stale evidence — most
    obviously earnings-call transcripts, which have a 120-day fetch window.
    """
    if thesis_created_at.tzinfo is None:
        thesis_created_at = thesis_created_at.replace(tzinfo=timezone.utc)
    floor = thesis_created_at - timedelta(days=1)

    surviving = []
    for candidate in candidates:
        if candidate.get("event_type") in _STATELESS_EVENT_TYPES:
            surviving.append(candidate)
            continue
        event_date = _candidate_event_date(candidate)
        if event_date is None or event_date >= floor:
            surviving.append(candidate)
    return surviving

# Cooldown hours per evidence_type (mapped from event_type before this runs)
COOLDOWN_HOURS: dict[str, int] = {
    "price_move": 24,
    "metric_breach": 24,
    "news": 48,
    "earnings": 48,
    "insider": 48,
}
DEFAULT_COOLDOWN_HOURS = 24

SEVERITY_RANK: dict[str, int] = {
    "info": 0,
    "warning": 1,
    "thesis_breaking": 2,
}

EVENT_SPECIFICITY_RANK: dict[str, int] = {
    "metric_threshold": 5,
    "earnings_call_transcript": 4,
    "earnings_surprise": 3,
    "insider_transaction": 3,
    "news_or_earnings_candidate": 2,
    "news_keyword_match": 2,
    "upcoming_earnings": 1,
    "price_move": 0,
}

EVIDENCE_TYPE_MAP: dict[str, str] = {
    "price_move": "price_move",
    "metric_threshold": "metric_breach",
    "news_or_earnings_candidate": "news",
    "earnings_surprise": "earnings",
    "upcoming_earnings": "earnings",
    "earnings_call_transcript": "earnings",
    "insider_transaction": "insider",
    "edgar_8k": "regulatory_filing",
    "gemini_news": "news",
    "news_keyword_match": "news",
}


def _get_evidence_source_id(evidence: dict[str, Any]) -> str | None:
    return (
        evidence.get("article_id")
        or evidence.get("transaction_id")
        or evidence.get("transcript_id")
        or evidence.get("edgar_accession")
    )


def _get_evidence_type(event_type: str) -> str:
    return EVIDENCE_TYPE_MAP.get(event_type, event_type)


def _normalize_datetime(timestamp: datetime) -> datetime:
    return timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)


def _event_evidence_type(event_type: str | None, raw_data: dict[str, Any] | None) -> str | None:
    if event_type:
        return event_type
    if not raw_data or not isinstance(raw_data, dict):
        return None
    candidate_type = raw_data.get("candidate_type")
    if isinstance(candidate_type, str):
        return _get_evidence_type(candidate_type)
    return None


async def _load_recent_evidence_keys(
    db: AsyncSession,
    holding_id: uuid.UUID,
    days: int = EVIDENCE_DEDUP_DAYS,
) -> set[tuple[str, str]]:
    """Load (evidence_type, source_id) pairs from recent events for this holding."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(MonitoringEvent.evidence_type, MonitoringEvent.raw_data, MonitoringEvent.event_type)
        .where(
            MonitoringEvent.holding_id == holding_id,
            MonitoringEvent.created_at >= cutoff,
        )
    )
    keys: set[tuple[str, str]] = set()
    for ev_type, raw_data, event_type in result:
        if not raw_data or not isinstance(raw_data, dict):
            continue
        evidence = raw_data.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        normalized_type = _event_evidence_type(ev_type, raw_data) or _get_evidence_type(event_type)
        if source_id and normalized_type:
            keys.add((normalized_type, source_id))
    return keys


def _apply_evidence_dedup(
    candidates: list[dict[str, Any]],
    existing_keys: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Rule 1: Skip candidates whose (evidence_type, source_id) already exists in recent events."""
    filtered = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        if source_id:
            ev_type = _get_evidence_type(candidate.get("event_type", ""))
            key = (ev_type, source_id)
            if key in existing_keys or key in seen:
                continue
            seen.add(key)
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
        cooldown_end = _normalize_datetime(signal.last_fired_at) + timedelta(hours=cooldown_hours)

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


def apply_priority_suppression(
    classified: list[tuple[dict[str, Any], str]],
) -> list[tuple[dict[str, Any], str]]:
    """Rule 3: If a thesis_breaking candidate exists, drop lower-severity candidates
    that share the same evidence source.

    Takes and returns a list of (candidate, severity) tuples.
    Call AFTER classification, BEFORE event persistence.
    """
    # Collect evidence sources from thesis_breaking candidates
    breaking_sources: set[str] = set()
    for candidate, severity in classified:
        if severity == "thesis_breaking":
            evidence = candidate.get("evidence", {})
            source_id = _get_evidence_source_id(evidence)
            if source_id:
                breaking_sources.add(source_id)

    if not breaking_sources:
        return _apply_sibling_specificity_suppression(classified)

    filtered = []
    for candidate, severity in classified:
        if severity == "thesis_breaking":
            filtered.append((candidate, severity))
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
        filtered.append((candidate, severity))

    return _apply_sibling_specificity_suppression(filtered)


def _candidate_family(event_type: str) -> str | None:
    if event_type in {
        "upcoming_earnings",
        "earnings_surprise",
        "earnings_call_transcript",
        "news_or_earnings_candidate",
        "news_keyword_match",
    }:
        return "fundamental"
    if event_type == "insider_transaction":
        return "insider"
    return None


def _sibling_group_key(candidate: dict[str, Any]) -> tuple[str, str, str] | None:
    event_type = candidate.get("event_type", "")
    family = _candidate_family(event_type)
    if family is None:
        return None
    evidence = candidate.get("evidence", {})
    signal_id = evidence.get("signal_id")
    claim_id = evidence.get("claim_id")
    if not signal_id and not claim_id:
        return None
    return (str(signal_id or ""), str(claim_id or ""), family)


def _candidate_specificity_tuple(candidate: dict[str, Any], severity: str) -> tuple[int, int]:
    event_type = candidate.get("event_type", "")
    return (
        SEVERITY_RANK.get(severity, 0),
        EVENT_SPECIFICITY_RANK.get(event_type, 0),
    )


def _apply_sibling_specificity_suppression(
    classified: list[tuple[dict[str, Any], str]],
) -> list[tuple[dict[str, Any], str]]:
    """Within the same claim/signal family, keep the strongest candidate.

    Example: if transcript, upcoming earnings, and generic news all map to the same
    thesis pillar, keep the most specific/highest-severity sibling instead of
    surfacing several weaker prompts about the same issue.
    """
    best_by_group: dict[tuple[str, str, str], tuple[dict[str, Any], str]] = {}

    for candidate, severity in classified:
        group_key = _sibling_group_key(candidate)
        if group_key is None:
            continue
        current_best = best_by_group.get(group_key)
        if current_best is None or _candidate_specificity_tuple(candidate, severity) > _candidate_specificity_tuple(*current_best):
            best_by_group[group_key] = (candidate, severity)

    if not best_by_group:
        return classified

    filtered: list[tuple[dict[str, Any], str]] = []
    for candidate, severity in classified:
        group_key = _sibling_group_key(candidate)
        if group_key is None:
            filtered.append((candidate, severity))
            continue
        best_candidate, best_severity = best_by_group[group_key]
        if candidate is best_candidate and severity == best_severity:
            filtered.append((candidate, severity))
            continue
        logger.debug(
            "Sibling specificity suppression: dropping %s in favor of %s for group %s",
            candidate.get("event_type"),
            best_candidate.get("event_type"),
            group_key,
        )
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


_NEWS_EVENT_TYPES = {"gemini_news", "news_or_earnings_candidate", "news_keyword_match"}


def _headline_prefix(text: str, words: int = 6) -> str:
    clean = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return " ".join(clean.split()[:words])


def _apply_cross_source_dedup(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate same-story news that arrived from multiple sources in one run.

    Uses (evidence_type_family, headline_prefix) as the key. Keeps the
    candidate with the higher event specificity rank; ties go to first seen.
    """
    seen: dict[tuple[str, str], int] = {}  # key → index in `kept`
    kept: list[dict[str, Any]] = []

    for candidate in candidates:
        event_type = candidate.get("event_type", "")
        if event_type not in _NEWS_EVENT_TYPES:
            kept.append(candidate)
            continue

        evidence = candidate.get("evidence", {})
        headline = evidence.get("headline", "") or candidate.get("description", "")
        prefix = _headline_prefix(headline)
        if not prefix:
            kept.append(candidate)
            continue

        key = ("news", prefix)
        if key not in seen:
            seen[key] = len(kept)
            kept.append(candidate)
        else:
            existing_idx = seen[key]
            existing = kept[existing_idx]
            # Prefer a candidate already linked to a signal (e.g. a qualitative
            # news_watch match) so dedup never strips the link/verdict in favour
            # of an unlinked duplicate; otherwise prefer higher event specificity.
            if _cross_source_rank(candidate) > _cross_source_rank(existing):
                kept[existing_idx] = candidate
                logger.debug(
                    "Cross-source dedup: replaced %s with %s for '%s'",
                    existing.get("event_type"),
                    event_type,
                    prefix,
                )

    return kept


def _cross_source_rank(candidate: dict[str, Any]) -> tuple[int, int]:
    has_signal = 1 if (candidate.get("evidence") or {}).get("signal_id") else 0
    return (has_signal, EVENT_SPECIFICITY_RANK.get(candidate.get("event_type", ""), 0))


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

    existing_keys = await _load_recent_evidence_keys(db, holding_id)

    # Rule 0: Cross-source dedup (same story from Gemini + Alpha Vantage in same run)
    candidates = _apply_cross_source_dedup(candidates)

    # Rule 1: Evidence dedup (scoped by evidence_type + source_id)
    candidates = _apply_evidence_dedup(candidates, existing_keys)

    # Rule 2: Signal cooldown
    candidates = _apply_signal_cooldown(candidates, signal_map, now)

    # Rule 3: Priority suppression is applied separately after classification
    # — call apply_priority_suppression() after classify_event() in the caller

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
