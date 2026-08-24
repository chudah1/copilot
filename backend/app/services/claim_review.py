"""Claim-level thesis review.

The unit of review is a claim, not a monitoring event: evidence accrues to a
claim's trail, and deterministic rules decide when the claim asks for review.
A check-in writes one ClaimReview row per decided claim under a shared
session_id; per-event actions shrink to a "not relevant" flag (ThesisReview),
which keeps feeding signal decay and relevance telemetry.
"""

from __future__ import annotations

import re
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
CASE_SECTION_FIELDS = (
    "why_own_it",
    "must_remain_true",
    "what_would_change_my_mind",
)
_SECTION_STOPWORDS = {
    "about", "after", "again", "against", "also", "because", "being", "could",
    "from", "have", "into", "keep", "more", "rather", "should", "their", "there",
    "these", "they", "this", "through", "under", "what", "when", "where", "which",
    "with", "would",
}


@dataclass
class ClaimCheckInState:
    claim_id: uuid.UUID | None  # None = thesis-level general bucket
    label: str
    case_section: str | None  # why_own_it | must_remain_true | what_would_change_my_mind
    status: str  # holds | weakened | broken — latest review, default holds
    last_reviewed_at: datetime | None
    needs_review: bool
    needs_review_reason: str
    supports_events: list[MonitoringEvent] = field(default_factory=list)
    threatens_events: list[MonitoringEvent] = field(default_factory=list)
    neutral_events: list[MonitoringEvent] = field(default_factory=list)


def _case_section_for_claim(claim, thesis: Thesis) -> str | None:
    raw = claim.raw_extraction_json or {}
    source_field = raw.get("source_field") if isinstance(raw, dict) else None
    if source_field in CASE_SECTION_FIELDS:
        return source_field

    # Existing decompositions predate source_field. Use a conservative lexical
    # fallback until the map is next rebuilt with explicit attribution.
    claim_words = {
        word
        for word in re.findall(r"[a-z0-9]+", (claim.claim_text or "").lower())
        if len(word) >= 4 and word not in _SECTION_STOPWORDS
    }
    if not claim_words:
        return None

    scores: list[tuple[float, str]] = []
    for field in CASE_SECTION_FIELDS:
        field_words = {
            word
            for word in re.findall(r"[a-z0-9]+", (getattr(thesis, field, None) or "").lower())
            if len(word) >= 4 and word not in _SECTION_STOPWORDS
        }
        overlap = len(claim_words & field_words)
        if overlap:
            scores.append((overlap / len(claim_words), field))
    scores.sort(reverse=True)
    if not scores or (len(scores) > 1 and scores[0][0] == scores[1][0]):
        return None
    return scores[0][1]


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
    buckets: list[tuple[uuid.UUID | None, str, str | None]] = [
        (claim.id, claim.claim_text, _case_section_for_claim(claim, thesis))
        for claim in claims
    ]
    buckets.append((None, GENERAL_BUCKET, None))
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

    for claim_id, label, case_section in buckets:
        review = latest_reviews.get(claim_id)
        cutoff = review.created_at if review else None
        bucket_events = [
            event
            for event in events_by_bucket.get(claim_id, [])
            if cutoff is None or (event.created_at and event.created_at > cutoff)
        ]
        supports = [e for e in bucket_events if e.verdict == "supports"]
        threatens = [
            e
            for e in bucket_events
            if e.verdict in ("threatens", "review")
            # Older monitoring rows predate explicit verdicts. Preserve their
            # warning semantics so the claim review and portfolio pulse agree
            # about whether they put pressure on the written case.
            or (e.verdict is None and e.severity in ("warning", "thesis_breaking"))
        ]
        neutral = [e for e in bucket_events if e not in supports and e not in threatens]
        needs, reason = _needs_review(threatens)
        states.append(
            ClaimCheckInState(
                claim_id=claim_id,
                label=label,
                case_section=case_section,
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
    (confidence steps down), invalidate, or rewrite. A rewrite keeps the thesis
    in needs_review until the revised case is actually saved by the editor.
    Raises ValueError on invalid input.
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
    check_in_states = {state.claim_id: state for state in await compute_check_in(db, thesis)}
    decision_claim_ids = [decision.get("claim_id") for decision in decisions]
    if len(decision_claim_ids) != len(set(decision_claim_ids)):
        raise ValueError("A claim can only be reviewed once per check-in")
    valid_claim_ids = set(check_in_states)
    invalid_claim_ids = [claim_id for claim_id in decision_claim_ids if claim_id not in valid_claim_ids]
    if invalid_claim_ids:
        raise ValueError("One or more claims do not belong to this thesis")

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

        # A claim-level decision resolves the evidence the investor just read.
        # Without these rows the check-in cutoff moved forward, but portfolio
        # pulse still saw the same events as unresolved and kept the position in
        # Changed after the decision was recorded.
        state = check_in_states.get(decision.get("claim_id"))
        if state is not None:
            if decision["status"] == "holds":
                action = "reaffirmed"
            elif decision["status"] == "weakened" or thesis_action != "invalidate":
                action = "lowered_confidence"
            else:
                action = "invalidated"
            for event in state.supports_events + state.threatens_events + state.neutral_events:
                db.add(
                    ThesisReview(
                        thesis_id=thesis.id,
                        monitoring_event_id=event.id,
                        action=action,
                        notes=notes,
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
        elif thesis_action == "rewrite":
            # Do not reactivate a case whose claim just broke. The editor can
            # explicitly move it back to active after the revised case saves.
            thesis.status = "needs_review"
    elif thesis.status != "invalidated":
        thesis.status = "active"
    thesis.updated_at = now

    counts = {status: sum(1 for d in decisions if d["status"] == status) for status in CLAIM_REVIEW_STATUSES}
    summary_bits = [f"{count} {status}" for status, count in sorted(counts.items()) if count]
    reviewed_parts = [
        check_in_states[decision.get("claim_id")].label
        for decision in decisions
        if decision.get("claim_id") in check_in_states
    ]
    bet_text = "; ".join(reviewed_parts) or thesis.why_own_it

    # Decision-mirror capture: a check-in is one position-level conviction call
    # (keep vs exit); claim verdicts are the detail. Best-effort, never raises.
    from app.services.decision_snapshots import capture_check_in_decision

    await capture_check_in_decision(
        db,
        thesis=thesis,
        holding=holding,
        bet_text=bet_text,
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
        content=f"Reviewed {len(decisions)} part{'s' if len(decisions) != 1 else ''} of the written case: {', '.join(summary_bits)}.",
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
