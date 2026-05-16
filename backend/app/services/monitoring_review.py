import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_review import ThesisReview
from app.models.thesis_signal import ThesisSignal
from app.services.conviction_log import EVIDENCE_REVIEWED, append_log_entry

logger = logging.getLogger(__name__)

VALID_REVIEW_ACTIONS = {
    "reaffirmed",
    "ignored",
    "lowered_confidence",
    "invalidated",
    "not_relevant",
}

IGNORE_ACTIONS = {"ignored", "not_relevant"}
SIGNAL_DECAY_THRESHOLD = 3


def _lower_confidence(current: str) -> str:
    if current == "high":
        return "medium"
    if current == "medium":
        return "low"
    return "low"


async def _load_signal(db: AsyncSession, signal_id) -> ThesisSignal | None:
    if signal_id is None:
        return None
    result = await db.execute(
        select(ThesisSignal).where(ThesisSignal.id == signal_id)
    )
    return result.scalar_one_or_none()


async def _rebuild_interpretation_cache(db: AsyncSession, thesis: Thesis) -> None:
    """Rebuild the interpretation cache after a signal is deactivated."""
    from app.services.decomposition import _sync_interpretation_cache

    result = await db.execute(
        select(ThesisDecomposition)
        .where(
            ThesisDecomposition.thesis_id == thesis.id,
            ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
        )
        .order_by(ThesisDecomposition.version.desc())
        .limit(1)
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
    )
    decomposition = result.scalar_one_or_none()
    if decomposition is None:
        return

    labels: list[str] = []
    for claim in decomposition.claims:
        if claim.claim_type and claim.claim_type not in labels:
            labels.append(claim.claim_type)

    active_signals = [
        signal
        for claim in decomposition.claims
        for entity in claim.entities
        for signal in entity.signals
        if signal.active
    ]

    _sync_interpretation_cache(
        thesis,
        reason_type=decomposition.reason_type,
        monitorability=decomposition.monitorability,
        labels=labels,
        active_signals=active_signals,
    )


async def review_monitoring_event(
    db: AsyncSession,
    *,
    event: MonitoringEvent,
    thesis: Thesis,
    action: str,
    notes: str | None,
) -> ThesisReview:
    if action not in VALID_REVIEW_ACTIONS:
        raise ValueError("Invalid review action")

    review = ThesisReview(
        thesis_id=thesis.id,
        monitoring_event_id=event.id,
        action=action,
        notes=notes,
    )
    db.add(review)

    now = datetime.now(timezone.utc)
    if action == "reaffirmed":
        if thesis.status == "invalidated":
            raise ValueError("Invalidated theses cannot be reaffirmed")
        thesis.status = "active"
        thesis.updated_at = now
    elif action in IGNORE_ACTIONS:
        if thesis.status != "invalidated":
            thesis.status = "active"
            thesis.updated_at = now
    elif action == "lowered_confidence":
        if thesis.status == "invalidated":
            raise ValueError("Invalidated theses cannot lower confidence")
        thesis.confidence = _lower_confidence(thesis.confidence)
        thesis.status = "active"
        thesis.updated_at = now
    elif action == "invalidated":
        thesis.status = "invalidated"
        thesis.invalidated_at = now
        thesis.invalidation_reason = notes or f"Invalidated after reviewing monitoring event: {event.title}"
        thesis.updated_at = now

    # Signal decay: track consecutive ignores
    signal = await _load_signal(db, event.signal_id)
    if signal is not None:
        if action in IGNORE_ACTIONS:
            signal.consecutive_ignores += 1
            if signal.consecutive_ignores >= SIGNAL_DECAY_THRESHOLD and signal.active:
                signal.active = False
                logger.info(
                    "Signal %s auto-deactivated after %d consecutive ignores",
                    signal.id,
                    signal.consecutive_ignores,
                )
                await _rebuild_interpretation_cache(db, thesis)
                # TODO: create in-app notification when UserNotification model exists
                # "We stopped watching {signal_label} because you've ignored it 3 times."
        else:
            signal.consecutive_ignores = 0

    # Conviction log: evidence reviewed
    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=event.holding_id,
        user_id=thesis.user_id,
        entry_type=EVIDENCE_REVIEWED,
        content=f"{action}: {event.summary[:200] if event.summary else event.title}",
        metadata={"action": action, "notes": notes, "event_id": str(event.id)},
        claim_id=event.claim_id,
        signal_id=event.signal_id,
    )

    await db.commit()
    await db.refresh(review)
    await db.refresh(thesis)
    return review
