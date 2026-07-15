"""Claim-level thesis review.

The unit of review is a claim, not a monitoring event: evidence accrues to a
claim's trail, and deterministic rules decide when the claim asks for review.
A check-in writes one ClaimReview row per decided claim under a shared
session_id; per-event actions shrink to a "not relevant" flag (ThesisReview),
which keeps feeding signal decay and relevance telemetry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.claim_review import ClaimReview
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_review import ThesisReview
from app.services.conviction_log import EVIDENCE_REVIEWED, append_log_entry
from app.services.signal_matching import load_active_decomposition

CLAIM_REVIEW_STATUSES = frozenset({"holds", "weakened", "broken"})
THESIS_ACTIONS = frozenset({"keep_lowered", "invalidate", "rewrite"})

# Deterministic needs-review thresholds. Supports/neutral evidence never asks.
WARNING_THREATENS_THRESHOLD = 2  # threatens at warning+ severity since last review
ANY_THREATENS_THRESHOLD = 4  # threatens at any severity since last review

GENERAL_BUCKET = "General evidence"


@dataclass
class ClaimCheckInState:
    claim_id: uuid.UUID | None  # None = thesis-level general bucket
    label: str
    status: str  # holds | weakened | broken — latest review, default holds
    last_reviewed_at: datetime | None
    needs_review: bool
    needs_review_reason: str
    supports_events: list[MonitoringEvent] = field(default_factory=list)
    threatens_events: list[MonitoringEvent] = field(default_factory=list)
    neutral_events: list[MonitoringEvent] = field(default_factory=list)


def _needs_review(threatens: list[MonitoringEvent]) -> tuple[bool, str]:
    if any(event.severity == "thesis_breaking" for event in threatens):
        return True, "A thesis-breaking event landed on this claim."
    strong = sum(1 for event in threatens if event.severity in ("warning", "thesis_breaking"))
    if strong >= WARNING_THREATENS_THRESHOLD:
        return True, f"{strong} warning-level events have accumulated against this claim."
    if len(threatens) >= ANY_THREATENS_THRESHOLD:
        return True, f"{len(threatens)} events have accumulated against this claim."
    return False, ""


async def _signal_to_claim_map(db: AsyncSession, thesis: Thesis) -> tuple[dict[uuid.UUID, uuid.UUID], list]:
    """Map signal_id -> parent claim_id via the claim -> entity -> signal tree."""
    decomposition = await load_active_decomposition(db, thesis.id)
    if decomposition is None:
        return {}, []
    mapping: dict[uuid.UUID, uuid.UUID] = {}
    for claim in decomposition.claims:
        for entity in claim.entities:
            for signal in entity.signals:
                mapping[signal.id] = claim.id
    return mapping, list(decomposition.claims)


async def _latest_reviews_by_claim(db: AsyncSession, thesis_id: uuid.UUID) -> dict[uuid.UUID | None, ClaimReview]:
    rows = await db.execute(
        select(ClaimReview)
        .where(ClaimReview.thesis_id == thesis_id)
        .order_by(ClaimReview.created_at.asc())
    )
    latest: dict[uuid.UUID | None, ClaimReview] = {}
    for row in rows.scalars().all():
        latest[row.claim_id] = row  # ascending order: last write wins
    return latest


async def compute_check_in(db: AsyncSession, thesis: Thesis) -> list[ClaimCheckInState]:
    signal_map, claims = await _signal_to_claim_map(db, thesis)
    latest_reviews = await _latest_reviews_by_claim(db, thesis.id)

    event_rows = await db.execute(
        select(MonitoringEvent)
        .where(MonitoringEvent.thesis_id == thesis.id)
        .options(selectinload(MonitoringEvent.reviews))
        .order_by(MonitoringEvent.created_at.desc())
    )
    events = [event for event in event_rows.scalars().all() if not event.reviews]

    states: list[ClaimCheckInState] = []
    buckets: list[tuple[uuid.UUID | None, str]] = [
        (claim.id, claim.claim_text) for claim in claims
    ]
    buckets.append((None, GENERAL_BUCKET))
    claim_ids = {claim.id for claim in claims}

    def bucket_for(event: MonitoringEvent) -> uuid.UUID | None:
        if event.claim_id and event.claim_id in claim_ids:
            return event.claim_id
        if event.signal_id and event.signal_id in signal_map:
            return signal_map[event.signal_id]
        return None

    events_by_bucket: dict[uuid.UUID | None, list[MonitoringEvent]] = {}
    for event in events:
        events_by_bucket.setdefault(bucket_for(event), []).append(event)

    for claim_id, label in buckets:
        review = latest_reviews.get(claim_id)
        cutoff = review.created_at if review else None
        bucket_events = [
            event
            for event in events_by_bucket.get(claim_id, [])
            if cutoff is None or (event.created_at and event.created_at > cutoff)
        ]
        supports = [e for e in bucket_events if e.verdict == "supports"]
        threatens = [e for e in bucket_events if e.verdict in ("threatens", "review")]
        neutral = [e for e in bucket_events if e not in supports and e not in threatens]
        needs, reason = _needs_review(threatens)
        states.append(
            ClaimCheckInState(
                claim_id=claim_id,
                label=label,
                status=review.status if review else "holds",
                last_reviewed_at=review.created_at if review else None,
                needs_review=needs,
                needs_review_reason=reason,
                supports_events=supports,
                threatens_events=threatens,
                neutral_events=neutral,
            )
        )
    return states


def _lower_confidence(current: str) -> str:
    if current == "high":
        return "medium"
    return "low"


async def submit_claim_reviews(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    user_id: uuid.UUID,
    decisions: list[dict],
    thesis_action: str | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    """Write one ClaimReview row per decision under a shared session_id.

    Any claim marked broken forces a thesis-level decision: keep_lowered
    (confidence steps down), invalidate, or rewrite (no mutation here — the
    client routes to the editor). Raises ValueError on invalid input.
    """
    if not decisions:
        raise ValueError("A check-in needs at least one claim decision")
    for decision in decisions:
        if decision.get("status") not in CLAIM_REVIEW_STATUSES:
            raise ValueError(f"Invalid claim status: {decision.get('status')!r}")
    if thesis.status == "invalidated":
        raise ValueError("Invalidated theses cannot be reviewed")

    any_broken = any(decision["status"] == "broken" for decision in decisions)
    if any_broken and thesis_action not in THESIS_ACTIONS:
        raise ValueError("A broken claim requires a thesis_action: keep_lowered, invalidate, or rewrite")

    now = datetime.now(timezone.utc)
    session_id = uuid.uuid4()
    for decision in decisions:
        db.add(
            ClaimReview(
                thesis_id=thesis.id,
                claim_id=decision.get("claim_id"),
                session_id=session_id,
                status=decision["status"],
                notes=decision.get("notes"),
                created_at=now,
            )
        )

    if any_broken:
        if thesis_action == "invalidate":
            broken_notes = next(
                (decision.get("notes") for decision in decisions if decision["status"] == "broken" and decision.get("notes")),
                None,
            )
            thesis.status = "invalidated"
            thesis.invalidated_at = now
            thesis.invalidation_reason = notes or broken_notes or "Invalidated at thesis check-in: a core claim broke."
        elif thesis_action == "keep_lowered":
            thesis.confidence = _lower_confidence(thesis.confidence)
            thesis.status = "active"
        # rewrite: rows are recorded; the client routes to the thesis editor.
    elif thesis.status != "invalidated":
        thesis.status = "active"
    thesis.updated_at = now

    counts = {status: sum(1 for d in decisions if d["status"] == status) for status in CLAIM_REVIEW_STATUSES}
    summary_bits = [f"{count} {status}" for status, count in sorted(counts.items()) if count]

    # Decision-mirror capture: a check-in is one position-level conviction call
    # (keep vs exit); claim verdicts are the detail. Best-effort, never raises.
    from app.services.decision_snapshots import capture_check_in_decision

    await capture_check_in_decision(
        db,
        thesis=thesis,
        holding=holding,
        claim_verdict_summary=f"Thesis check-in: {', '.join(summary_bits)}.",
        exited=thesis.status == "invalidated",
        notes=notes,
        now=now,
    )

    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=user_id,
        entry_type=EVIDENCE_REVIEWED,
        content=f"Thesis check-in: {', '.join(summary_bits)}.",
        metadata={
            "session_id": str(session_id),
            "decisions": [
                {
                    "claim_id": str(d["claim_id"]) if d.get("claim_id") else None,
                    "status": d["status"],
                }
                for d in decisions
            ],
            "thesis_action": thesis_action,
        },
    )
    return session_id
