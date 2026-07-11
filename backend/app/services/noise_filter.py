from __future__ import annotations

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

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
    *,
    min_lookback_days: int = 0,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Drop event-dated candidates that predate this thesis.

    Stateless candidates (earnings_surprise, metric_threshold, etc.) reflect
    current market state rather than a discrete past event, so they are always
    kept. Everything else is filtered if its event date is before the thesis was
    created (minus one day of grace for timezone / scheduling skew).

    Prevents new users from receiving alerts about stale evidence — most
    obviously earnings-call transcripts, which have a 120-day fetch window.

    min_lookback_days extends the floor for on-demand runs so a brand-new user
    hitting check-now (or first pulse right after onboarding) sees the last N
    days of relevant filings/news, rather than nothing because every event
    predates a thesis they wrote minutes ago. Only pulls the floor earlier;
    for older theses the thesis-created-at date wins so we don't resurface a
    year of already-processed history.
    """
    if thesis_created_at.tzinfo is None:
        thesis_created_at = thesis_created_at.replace(tzinfo=timezone.utc)
    floor = thesis_created_at - timedelta(days=1)
    if min_lookback_days > 0:
        current_time = now or datetime.now(timezone.utc)
        lookback_floor = current_time - timedelta(days=min_lookback_days)
        floor = min(floor, lookback_floor)

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
    "analyst_revision": 72,
}
DEFAULT_COOLDOWN_HOURS = 24
COARSE_COOLDOWN_EVENT_TYPES = frozenset({
    "price_move",
    "metric_threshold",
    "upcoming_earnings",
    "earnings_surprise",
    "monitoring_inactive",
})

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
    "product_ramp_update": 3,
    "news_or_earnings_candidate": 2,
    "news_keyword_match": 2,
    "analyst_revision": 2,
    "upcoming_earnings": 1,
    "price_move": 0,
}

EVIDENCE_TYPE_MAP: dict[str, str] = {
    "price_move": "price_move",
    "metric_threshold": "metric_breach",
    "news_or_earnings_candidate": "news",
    "product_ramp_update": "news",
    "earnings_surprise": "earnings",
    "upcoming_earnings": "earnings",
    "earnings_call_transcript": "earnings",
    "insider_transaction": "insider",
    "edgar_8k": "regulatory_filing",
    "gemini_news": "news",
    "news_keyword_match": "news",
    "analyst_revision": "analyst_revision",
}


def _get_evidence_source_id(evidence: dict[str, Any]) -> str | None:
    return (
        evidence.get("article_id")
        or evidence.get("transaction_id")
        or evidence.get("transcript_id")
        or evidence.get("edgar_accession")
        or evidence.get("analyst_revision_id")
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


def _normalize_story_date(raw: Any) -> str | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            try:
                return date.fromisoformat(raw[:10]).isoformat()
            except ValueError:
                return None
    return None


def _story_anchor_uses_cooldown(event_type: str) -> bool:
    return event_type not in COARSE_COOLDOWN_EVENT_TYPES


def story_anchor_for_candidate(candidate: dict[str, Any]) -> str | None:
    evidence = candidate.get("evidence", {})
    event_type = str(candidate.get("event_type", "") or "").strip()
    if not event_type:
        return None

    source_id = _get_evidence_source_id(evidence)
    if source_id:
        return f"{event_type}:source:{source_id}"

    if event_type in {"earnings_call_transcript", "upcoming_earnings"}:
        quarter = str(evidence.get("quarter") or "").strip()
        if quarter:
            return f"{event_type}:earnings_cycle:{quarter}"
        call_date = _normalize_story_date(evidence.get("call_date") or evidence.get("date"))
        if call_date:
            return f"{event_type}:earnings_cycle:{call_date}"

    if event_type == "insider_transaction":
        transaction_date = _normalize_story_date(evidence.get("transaction_date") or evidence.get("date"))
        if transaction_date:
            actor = str(
                evidence.get("insider_name")
                or evidence.get("owner_name")
                or evidence.get("reporting_name")
                or ""
            ).strip().lower()
            if actor:
                return f"{event_type}:insider:{transaction_date}:{actor}"
            return f"{event_type}:insider:{transaction_date}"

    if event_type == "edgar_8k":
        filing_date = _normalize_story_date(evidence.get("filing_date") or evidence.get("date"))
        items = evidence.get("items")
        item_key = ""
        if isinstance(items, list) and items:
            item_key = ",".join(sorted(str(item).strip() for item in items if str(item).strip()))
        headline = str(evidence.get("headline") or evidence.get("description") or "").strip()
        prefix = _headline_prefix(headline, words=5)
        parts = [part for part in (filing_date, item_key, prefix) if part]
        if parts:
            return f"{event_type}:filing:{':'.join(parts)}"

    headline = str(evidence.get("headline") or candidate.get("description") or "").strip()
    prefix = _headline_prefix(headline, words=5)
    if not prefix:
        return None
    story_date = _normalize_story_date(
        evidence.get("published_at")
        or evidence.get("date")
        or evidence.get("filing_date")
        or evidence.get("event_date")
    )
    if story_date:
        return f"{event_type}:headline:{story_date}:{prefix}"
    return f"{event_type}:headline:{prefix}"


def _story_anchor_from_event(
    event_type: str | None,
    story_anchor: str | None,
    raw_data: dict[str, Any] | None,
) -> str | None:
    if story_anchor:
        return story_anchor
    if not event_type or not raw_data or not isinstance(raw_data, dict):
        return None
    evidence = raw_data.get("evidence")
    if not isinstance(evidence, dict):
        return None
    return story_anchor_for_candidate({
        "event_type": event_type,
        "evidence": evidence,
    })


async def _load_recent_signal_story_anchors(
    db: AsyncSession,
    holding_id: uuid.UUID,
    signal_ids: set[str],
    *,
    cutoff: datetime,
) -> dict[str, list[tuple[datetime, str]]]:
    """Load recent story anchors for the active signals in this pass.

    Recent monitoring_events are the source of truth. We fall back to deriving
    an anchor from legacy raw_data when the persisted story_anchor column is
    still null during rollout.
    """
    if not signal_ids:
        return {}

    signal_uuids: list[uuid.UUID] = []
    for signal_id in signal_ids:
        try:
            signal_uuids.append(uuid.UUID(str(signal_id)))
        except (TypeError, ValueError):
            continue
    if not signal_uuids:
        return {}

    result = await db.execute(
        select(
            MonitoringEvent.signal_id,
            MonitoringEvent.story_anchor,
            MonitoringEvent.raw_data,
            MonitoringEvent.event_type,
            MonitoringEvent.created_at,
        ).where(
            MonitoringEvent.holding_id == holding_id,
            MonitoringEvent.signal_id.in_(signal_uuids),
            MonitoringEvent.created_at >= cutoff,
        )
    )

    anchors_by_signal: dict[str, list[tuple[datetime, str]]] = {}
    for signal_id, stored_anchor, raw_data, event_type, created_at in result:
        if signal_id is None or created_at is None:
            continue
        anchor = _story_anchor_from_event(event_type, stored_anchor, raw_data)
        if not anchor:
            continue
        signal_id_str = str(signal_id)
        anchors_by_signal.setdefault(signal_id_str, []).append((_normalize_datetime(created_at), anchor))
    return anchors_by_signal


def _apply_evidence_dedup(
    candidates: list[dict[str, Any]],
    existing_keys: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Rule 1: Skip candidates whose (evidence_type, source_id) already exists in recent events."""
    filtered: list[dict[str, Any]] = []
    seen: dict[tuple[str, str], int] = {}
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        source_id = _get_evidence_source_id(evidence)
        if source_id:
            ev_type = _get_evidence_type(candidate.get("event_type", ""))
            key = (ev_type, source_id)
            if key in existing_keys:
                continue
            existing_idx = seen.get(key)
            if existing_idx is not None:
                existing = filtered[existing_idx]
                if _cross_source_rank(candidate) > _cross_source_rank(existing):
                    filtered[existing_idx] = candidate
                continue
            seen[key] = len(filtered)
        filtered.append(candidate)
    return filtered


def _candidate_log_token(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence", {})
    event_type = str(candidate.get("event_type", "") or "").strip() or "unknown"
    parts = [f"type={event_type}"]

    signal_id = str(evidence.get("signal_id") or "").strip()
    if signal_id:
        parts.append(f"signal={signal_id[:8]}")

    source_id = str(_get_evidence_source_id(evidence) or "").strip()
    if source_id:
        parts.append(f"source={source_id[:16]}")

    anchor = story_anchor_for_candidate(candidate)
    if anchor:
        parts.append(f"anchor={anchor[:80]}")
    else:
        headline = str(evidence.get("headline") or candidate.get("description") or "").strip()
        prefix = _headline_prefix(headline, words=5)
        if prefix:
            parts.append(f"headline={prefix[:40]}")

    return " ".join(parts)


def _log_filter_rule_drops(
    rule_name: str,
    *,
    holding_id: uuid.UUID,
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> None:
    kept_ids = {id(candidate) for candidate in after}
    dropped = [candidate for candidate in before if id(candidate) not in kept_ids]
    if not dropped:
        return
    samples = " | ".join(_candidate_log_token(candidate) for candidate in dropped[:3])
    # WARNING so it survives Railway's default log level; INFO app-code lines
    # get silently dropped under uvicorn's default config — same reason we
    # bumped Gemini diagnostics in 303b9f3.
    logger.warning(
        "Noise filter %s dropped %d/%d candidates for holding %s; samples=%s",
        rule_name,
        len(dropped),
        len(before),
        holding_id,
        samples,
    )


def _apply_signal_cooldown(
    candidates: list[dict[str, Any]],
    signal_map: dict[str, ThesisSignal],
    recent_story_anchors: dict[str, list[tuple[datetime, str]]] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Rule 2: Skip candidates whose signal fired within the cooldown window."""
    now = now or datetime.now(timezone.utc)
    recent_story_anchors = recent_story_anchors or {}
    filtered = []
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        signal_id = evidence.get("signal_id")
        if not signal_id:
            filtered.append(candidate)
            continue

        event_type = candidate.get("event_type", "")
        evidence_type = _get_evidence_type(candidate.get("event_type", ""))
        cooldown_hours = COOLDOWN_HOURS.get(evidence_type, DEFAULT_COOLDOWN_HOURS)
        signal_id_str = str(signal_id)

        if _story_anchor_uses_cooldown(event_type):
            candidate_anchor = story_anchor_for_candidate(candidate)
            if candidate_anchor:
                cooldown_start = now - timedelta(hours=cooldown_hours)
                recent_anchors = recent_story_anchors.get(signal_id_str, [])
                matched_recent = next(
                    (
                        (created_at, anchor)
                        for created_at, anchor in recent_anchors
                        if anchor == candidate_anchor and created_at >= cooldown_start
                    ),
                    None,
                )
                if matched_recent is not None:
                    matched_at, matched_anchor = matched_recent
                    logger.debug(
                        "Signal cooldown: skipping %s for signal %s due to matching story anchor %s from %s",
                        event_type,
                        signal_id_str,
                        matched_anchor,
                        matched_at.isoformat(),
                    )
                    continue
                filtered.append(candidate)
                continue

        signal = signal_map.get(signal_id_str)
        if not signal or not signal.last_fired_at:
            filtered.append(candidate)
            continue

        cooldown_end = _normalize_datetime(signal.last_fired_at) + timedelta(hours=cooldown_hours)

        if now < cooldown_end:
            logger.debug(
                "Signal cooldown: skipping %s for signal %s (cooldown until %s)",
                event_type,
                signal_id_str,
                cooldown_end.isoformat(),
            )
            continue
        filtered.append(candidate)
    return filtered


def apply_priority_suppression(
    classified: list[tuple[dict[str, Any], str]],
    *,
    limit_info_news_per_signal: bool = True,
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
        filtered = _apply_sibling_specificity_suppression(classified)
        if limit_info_news_per_signal:
            filtered = _apply_same_signal_info_news_cap(filtered)
        return filtered

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

    filtered = _apply_sibling_specificity_suppression(filtered)
    if limit_info_news_per_signal:
        filtered = _apply_same_signal_info_news_cap(filtered)
    return filtered


def _candidate_family(event_type: str) -> str | None:
    if event_type in {
        "upcoming_earnings",
        "earnings_surprise",
        "earnings_call_transcript",
        "news_or_earnings_candidate",
        "news_keyword_match",
        # gemini_news was missing from the fundamental family, so sibling
        # specificity suppression skipped it — 10 outlets covering the same
        # Q2-deliveries story all landed as 10 separate events on the same
        # signal. Grouping gemini_news with the other news-shaped events
        # collapses same-signal duplicates to the strongest single item.
        "gemini_news",
    }:
        return "fundamental"
    if event_type == "insider_transaction":
        return "insider"
    return None


def _sibling_story_key(candidate: dict[str, Any]) -> str | None:
    evidence = candidate.get("evidence", {})
    source_id = _get_evidence_source_id(evidence)
    if source_id:
        return f"source:{source_id}"

    event_type = candidate.get("event_type", "")
    if event_type in {"earnings_call_transcript", "upcoming_earnings", "earnings_surprise"}:
        quarter = str(evidence.get("quarter") or "").strip()
        if quarter:
            return f"earnings_cycle:{quarter}"
        call_date = _normalize_story_date(evidence.get("call_date") or evidence.get("date"))
        if call_date:
            return f"earnings_cycle:{call_date}"

    if event_type == "insider_transaction":
        transaction_date = _normalize_story_date(evidence.get("transaction_date") or evidence.get("date"))
        if transaction_date:
            return f"insider:{transaction_date}"

    headline = str(evidence.get("headline") or candidate.get("description") or "").strip()
    prefix = _headline_prefix(headline, words=5)
    if not prefix:
        return None
    story_date = _normalize_story_date(
        evidence.get("published_at")
        or evidence.get("date")
        or evidence.get("filing_date")
        or evidence.get("event_date")
    )
    if story_date:
        return f"headline:{story_date}:{prefix}"
    return f"headline:{prefix}"


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
    story_key = _sibling_story_key(candidate)
    if story_key is None:
        return (str(signal_id or ""), str(claim_id or ""), family)
    return (str(signal_id or ""), str(claim_id or ""), f"{family}:{story_key}")


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


_NEWS_EVENT_TYPES = {"gemini_news", "news_or_earnings_candidate", "product_ramp_update", "news_keyword_match"}
MAX_INFO_NEWS_EVENTS_PER_SIGNAL_PER_RUN = 2
_EDITORIAL_NOISE_PATTERNS = (
    "swot analysis",
    "morning call",
    "pick-and-shovel",
    "supercycle",
    "community",
    "price prediction",
    "stock forecast",
    "stock analysis",
    "market outlook",
    "newsletter",
    "news digest",
)


def _headline_prefix(text: str, words: int = 6) -> str:
    clean = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return " ".join(clean.split()[:words])


def _is_editorial_noise_candidate(candidate: dict[str, Any]) -> bool:
    evidence = candidate.get("evidence", {})
    headline = str(evidence.get("headline") or candidate.get("description") or "").lower()
    summary = str(evidence.get("summary") or "").lower()
    url = str(evidence.get("url") or "").lower()
    source = str(evidence.get("source") or "").lower()
    domain = urlparse(url).netloc.lower() if url else ""
    haystack = " ".join(part for part in (headline, summary, source, domain) if part)
    return any(pattern in haystack for pattern in _EDITORIAL_NOISE_PATTERNS)


def _info_news_guardrail_group_key(candidate: dict[str, Any], severity: str) -> tuple[str, str] | None:
    if severity != "info":
        return None
    event_type = candidate.get("event_type", "")
    if event_type not in _NEWS_EVENT_TYPES:
        return None
    evidence = candidate.get("evidence", {})
    signal_id = evidence.get("signal_id")
    claim_id = evidence.get("claim_id")
    if not signal_id and not claim_id:
        return None
    return (str(signal_id or ""), str(claim_id or ""))


def _info_news_guardrail_rank(candidate: dict[str, Any], severity: str) -> tuple[int, int, int, int]:
    evidence = candidate.get("evidence", {})
    return (
        0 if _is_editorial_noise_candidate(candidate) else 1,
        1 if evidence.get("url") else 0,
        EVENT_SPECIFICITY_RANK.get(candidate.get("event_type", ""), 0),
        1 if (evidence.get("matched_topics") or evidence.get("topic_context")) else 0,
    )


def _apply_same_signal_info_news_cap(
    classified: list[tuple[dict[str, Any], str]],
    *,
    max_items_per_signal: int = MAX_INFO_NEWS_EVENTS_PER_SIGNAL_PER_RUN,
) -> list[tuple[dict[str, Any], str]]:
    """Cap same-signal info/news bursts after classification."""
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any], str]]] = {}
    for idx, (candidate, severity) in enumerate(classified):
        group_key = _info_news_guardrail_group_key(candidate, severity)
        if group_key is None:
            continue
        grouped.setdefault(group_key, []).append((idx, candidate, severity))

    if not grouped:
        return classified

    allowed_ids: set[int] = set()
    dropped_by_group: list[tuple[tuple[str, str], list[tuple[dict[str, Any], str]]]] = []
    for group_key, items in grouped.items():
        if len(items) <= max_items_per_signal:
            allowed_ids.update(id(candidate) for _, candidate, _ in items)
            continue
        ranked = sorted(
            items,
            key=lambda item: (_info_news_guardrail_rank(item[1], item[2]), -item[0]),
            reverse=True,
        )
        kept = ranked[:max_items_per_signal]
        dropped = ranked[max_items_per_signal:]
        allowed_ids.update(id(candidate) for _, candidate, _ in kept)
        dropped_by_group.append((group_key, [(candidate, severity) for _, candidate, severity in dropped]))

    if not dropped_by_group:
        return classified

    for group_key, dropped_items in dropped_by_group:
        logger.info(
            "Post-classification info-news cap dropped %d candidates for group %s; samples=%s",
            len(dropped_items),
            group_key,
            " | ".join(_candidate_log_token(candidate) for candidate, _severity in dropped_items[:3]),
        )

    filtered: list[tuple[dict[str, Any], str]] = []
    for candidate, severity in classified:
        group_key = _info_news_guardrail_group_key(candidate, severity)
        if group_key is None or id(candidate) in allowed_ids:
            filtered.append((candidate, severity))
    return filtered


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
    skip_cooldown: bool = False,
) -> list[dict[str, Any]]:
    """Apply all noise suppression rules. Call after signal matching, before event creation."""
    if not candidates:
        return candidates

    existing_keys = await _load_recent_evidence_keys(db, holding_id)

    # Rule 0: Cross-source dedup (same story from Gemini + Alpha Vantage in same run)
    before_rule0 = list(candidates)
    candidates = _apply_cross_source_dedup(candidates)
    _log_filter_rule_drops("rule0_cross_source", holding_id=holding_id, before=before_rule0, after=candidates)

    # Rule 1: Evidence dedup (scoped by evidence_type + source_id)
    before_rule1 = list(candidates)
    candidates = _apply_evidence_dedup(candidates, existing_keys)
    _log_filter_rule_drops("rule1_recent_evidence", holding_id=holding_id, before=before_rule1, after=candidates)

    # Rule 2: Signal cooldown (skipped for non-persisting runs, e.g. historical audit)
    if not skip_cooldown:
        before_rule2 = list(candidates)
        story_signal_ids = {
            str((candidate.get("evidence") or {}).get("signal_id"))
            for candidate in candidates
            if _story_anchor_uses_cooldown(candidate.get("event_type", ""))
            and (candidate.get("evidence") or {}).get("signal_id")
        }
        recent_story_anchors: dict[str, list[tuple[datetime, str]]] = {}
        if story_signal_ids:
            current_time = now or datetime.now(timezone.utc)
            max_story_cooldown = max(
                COOLDOWN_HOURS.get(_get_evidence_type(candidate.get("event_type", "")), DEFAULT_COOLDOWN_HOURS)
                for candidate in candidates
                if _story_anchor_uses_cooldown(candidate.get("event_type", ""))
                and (candidate.get("evidence") or {}).get("signal_id")
            )
            recent_story_anchors = await _load_recent_signal_story_anchors(
                db,
                holding_id,
                story_signal_ids,
                cutoff=current_time - timedelta(hours=max_story_cooldown),
            )
        candidates = _apply_signal_cooldown(
            candidates,
            signal_map,
            recent_story_anchors=recent_story_anchors,
            now=now,
        )
        _log_filter_rule_drops("rule2_signal_cooldown", holding_id=holding_id, before=before_rule2, after=candidates)

    # Rule 3: Priority suppression is applied separately after classification
    # — call apply_priority_suppression() after classify_event() in the caller

    # Rule 4: Minimum relevance
    before_rule4 = list(candidates)
    candidates = _apply_minimum_relevance(candidates)
    _log_filter_rule_drops("rule4_minimum_relevance", holding_id=holding_id, before=before_rule4, after=candidates)

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
