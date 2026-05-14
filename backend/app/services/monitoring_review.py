from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_review import ThesisReview


VALID_REVIEW_ACTIONS = {
    "reaffirmed",
    "ignored",
    "lowered_confidence",
    "invalidated",
}


def _lower_confidence(current: str) -> str:
    if current == "high":
        return "medium"
    if current == "medium":
        return "low"
    return "low"


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
    elif action == "ignored":
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

    await db.commit()
    await db.refresh(review)
    await db.refresh(thesis)
    return review
