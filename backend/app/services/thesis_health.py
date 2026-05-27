from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.monitoring_event import MonitoringEvent
    from app.models.thesis_claim import ThesisClaim
    from app.models.thesis import Thesis
    from app.models.thesis_decomposition import ThesisDecomposition

_DECAY_HALF_LIFE_DAYS = 30
_THESIS_BREAKING_DECAY_FLOOR = 0.5

_EVENT_WEIGHTS: dict[tuple[str, str], int] = {
    ("thesis_breaking", "threatens"): -30,
    ("thesis_breaking", "review"):    -20,
    ("thesis_breaking", "neutral"):   -20,
    ("warning",         "threatens"): -15,
    ("warning",         "review"):    -8,
    ("warning",         "neutral"):   -5,
    ("info",            "neutral"):   -2,
}
_SUPPORTS_BONUS = 5

_CLAIM_MULTIPLIER_MIN = 0.5
_CLAIM_MULTIPLIER_MAX = 1.5


def _band(score: int) -> str:
    if score >= 75:
        return "Healthy"
    if score >= 45:
        return "At Risk"
    return "Broken"


def _decay_factor(event_age_days: float, severity: str, reviewed: bool) -> float:
    factor = 0.5 ** (event_age_days / _DECAY_HALF_LIFE_DAYS)
    if severity == "thesis_breaking" and not reviewed:
        factor = max(factor, _THESIS_BREAKING_DECAY_FLOOR)
    return factor


def _claim_multiplier(claim_confidence: float | None) -> float:
    if claim_confidence is None:
        return 1.0
    return max(_CLAIM_MULTIPLIER_MIN, min(_CLAIM_MULTIPLIER_MAX, claim_confidence * _CLAIM_MULTIPLIER_MAX))


def compute_health_score(
    decomposition_confidence: float | None,
    events: list[MonitoringEvent],
    claims: list[ThesisClaim],
    reviewed_event_ids: set[uuid.UUID],
    now: datetime | None = None,
) -> tuple[int, str]:
    if now is None:
        now = datetime.now(timezone.utc)

    if decomposition_confidence is not None:
        base = round(decomposition_confidence * 100)
        base = max(45, min(100, base))
    else:
        base = 75

    claims_by_id: dict[uuid.UUID, ThesisClaim] = {c.id: c for c in claims}

    delta = 0.0
    for event in events:
        verdict = event.verdict or "review"
        severity = event.severity

        if verdict == "supports":
            delta += _SUPPORTS_BONUS
            continue

        base_weight = _EVENT_WEIGHTS.get((severity, verdict), -5)

        created = event.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = (now - created).total_seconds() / 86400
        decay = _decay_factor(age_days, severity, event.id in reviewed_event_ids)

        claim_conf = None
        if event.claim_id and event.claim_id in claims_by_id:
            conf = claims_by_id[event.claim_id].confidence
            claim_conf = float(conf) if conf is not None else None
        multiplier = _claim_multiplier(claim_conf)

        delta += base_weight * decay * multiplier

    score = int(max(0, min(100, base + delta)))
    return score, _band(score)


async def refresh_thesis_health(
    db: AsyncSession,
    thesis: Thesis,
    claims: list[ThesisClaim] | None,
    decomposition: ThesisDecomposition | None,
    now: datetime | None = None,
) -> tuple[int, str, str | None]:
    from app.models.monitoring_event import MonitoringEvent
    from app.models.conviction_log_entry import ConvictionLogEntry

    events_result = await db.execute(
        select(MonitoringEvent).where(MonitoringEvent.thesis_id == thesis.id)
    )
    events = list(events_result.scalars().all())

    reviewed_result = await db.execute(
        select(ConvictionLogEntry.signal_id, ConvictionLogEntry.claim_id)
        .where(ConvictionLogEntry.thesis_id == thesis.id)
        .where(ConvictionLogEntry.entry_type == "evidence_reviewed")
    )
    reviewed_rows = reviewed_result.all()
    reviewed_signal_ids: set[uuid.UUID] = set()
    reviewed_claim_ids: set[uuid.UUID] = set()
    for row in reviewed_rows:
        if row.signal_id:
            reviewed_signal_ids.add(row.signal_id)
        if row.claim_id:
            reviewed_claim_ids.add(row.claim_id)

    event_ids_for_reviewed: set[uuid.UUID] = set()
    for event in events:
        sig_reviewed = event.signal_id and event.signal_id in reviewed_signal_ids
        claim_reviewed = event.claim_id and event.claim_id in reviewed_claim_ids
        if sig_reviewed or claim_reviewed:
            event_ids_for_reviewed.add(event.id)

    decomp_confidence = float(decomposition.decomposition_confidence) if (
        decomposition and decomposition.decomposition_confidence is not None
    ) else None

    score, label = compute_health_score(
        decomposition_confidence=decomp_confidence,
        events=events,
        claims=list(claims) if claims else [],
        reviewed_event_ids=event_ids_for_reviewed,
        now=now,
    )

    prev_label = thesis.health_label
    thesis.health_score = score
    thesis.health_label = label

    return score, label, prev_label


_BAND_ORDER = {"Healthy": 2, "At Risk": 1, "Broken": 0}


async def maybe_notify_band_drop(
    user_email: str,
    ticker: str,
    prev_label: str | None,
    new_label: str,
    score: int,
) -> None:
    from app.services.email import send_health_band_drop_email

    if prev_label is None or prev_label == new_label:
        return
    if _BAND_ORDER.get(new_label, 0) >= _BAND_ORDER.get(prev_label, 2):
        return  # improvement or same level — don't notify
    await send_health_band_drop_email(
        to_email=user_email,
        ticker=ticker,
        prev_label=prev_label,
        new_label=new_label,
        score=score,
    )
