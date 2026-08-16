from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_snapshot import DecisionSnapshot
from app.models.dashboard_coach_advice import DashboardCoachAdvice
from app.schemas.dashboard import (
    DashboardCoachFeedbackResponse,
    DashboardCoachMemoryResponse,
    DashboardCoachModeStatsResponse,
)

VALID_EVENTS = {"presented", "acted", "skipped"}
ADVICE_LINK_WINDOW_DAYS = 7


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _latest_feedback(row: DashboardCoachAdvice) -> tuple[datetime | None, str | None]:
    candidates = [
        (_as_utc(row.last_presented_at), "presented"),
        (_as_utc(row.last_acted_at), "acted"),
        (_as_utc(row.last_skipped_at), "skipped"),
    ]
    seen = [(timestamp, label) for timestamp, label in candidates if timestamp is not None]
    if not seen:
        return None, None
    return max(seen, key=lambda item: item[0])


async def get_dashboard_coach_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> DashboardCoachMemoryResponse:
    rows = (
        await db.execute(
            select(DashboardCoachAdvice).where(DashboardCoachAdvice.user_id == user_id)
        )
    ).scalars().all()

    mode_stats: dict[str, DashboardCoachModeStatsResponse] = {}
    total_presented = 0
    acted_count = 0
    skipped_count = 0
    last_feedback_at: datetime | None = None
    last_feedback: str | None = None
    last_mode: str | None = None

    for row in rows:
        total_presented += row.presented_count
        acted_count += row.acted_count
        skipped_count += row.skipped_count

        stats = mode_stats.get(row.mode)
        if stats is None:
            stats = DashboardCoachModeStatsResponse()
            mode_stats[row.mode] = stats
        stats.presented_count += row.presented_count
        stats.acted_count += row.acted_count
        stats.skipped_count += row.skipped_count
        if row.resolved_at is not None:
            stats.resolved_count += 1
        if row.outcome_kind == "helped":
            stats.helpful_count += 1
        elif row.outcome_kind == "hurt":
            stats.hurt_count += 1

        row_last_at, row_last_feedback = _latest_feedback(row)
        if row_last_at and row_last_feedback and (last_feedback_at is None or row_last_at > last_feedback_at):
            last_feedback_at = row_last_at
            last_feedback = row_last_feedback
            last_mode = row.mode

    return DashboardCoachMemoryResponse(
        total_presented=total_presented,
        acted_count=acted_count,
        skipped_count=skipped_count,
        last_feedback=last_feedback,
        last_mode=last_mode,
        mode_stats=mode_stats,
    )


def classify_snapshot_outcome(snapshot: DecisionSnapshot) -> str | None:
    resolution = snapshot.resolution_json or {}

    if snapshot.bucket == "dismissed":
        followthrough = (resolution.get("claim_followthrough") or {}).get("broke_after")
        if followthrough is True:
            return "hurt"
        if followthrough is False:
            return "helped"
        return None

    conditions = [
        item.get("held")
        for item in (resolution.get("conditions") or [])
        if item.get("held") in (True, False)
    ]
    if not conditions:
        return None

    broke = any(value is False for value in conditions)
    if snapshot.bucket == "held":
        return "hurt" if broke else "helped"
    if snapshot.bucket == "exited":
        return "helped" if broke else "hurt"
    return None


async def record_dashboard_coach_feedback(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    advice_key: str,
    mode: str,
    event: str,
    holding_id: uuid.UUID | None = None,
    thesis_id: uuid.UUID | None = None,
    loop_key: str | None = None,
    pattern_kind: str | None = None,
    action_label: str | None = None,
    now: datetime | None = None,
) -> DashboardCoachFeedbackResponse:
    if event not in VALID_EVENTS:
        raise ValueError(f"Unsupported coach feedback event: {event}")

    reference_now = now or datetime.now(timezone.utc)
    row = (
        await db.execute(
            select(DashboardCoachAdvice).where(
                DashboardCoachAdvice.user_id == user_id,
                DashboardCoachAdvice.advice_key == advice_key,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = DashboardCoachAdvice(
            user_id=user_id,
            advice_key=advice_key,
            mode=mode,
            holding_id=holding_id,
            thesis_id=thesis_id,
            loop_key=loop_key,
            pattern_kind=pattern_kind,
            status="presented",
            presented_count=0,
            acted_count=0,
            skipped_count=0,
        )
        db.add(row)

    row.mode = mode
    row.holding_id = holding_id
    row.thesis_id = thesis_id
    row.loop_key = loop_key
    row.pattern_kind = pattern_kind
    row.updated_at = reference_now

    if event == "presented":
        row.status = "presented"
        row.presented_count += 1
        row.first_presented_at = row.first_presented_at or reference_now
        row.last_presented_at = reference_now
    elif event == "acted":
        row.status = "acted"
        if row.presented_count == 0:
            row.presented_count = 1
            row.first_presented_at = row.first_presented_at or reference_now
        row.acted_count += 1
        row.last_acted_at = reference_now
        row.last_action_label = action_label
        if row.first_presented_at is None:
            row.first_presented_at = reference_now
        row.last_presented_at = row.last_presented_at or reference_now
    elif event == "skipped":
        row.status = "skipped"
        if row.presented_count == 0:
            row.presented_count = 1
            row.first_presented_at = row.first_presented_at or reference_now
        row.skipped_count += 1
        row.last_skipped_at = reference_now
        if row.first_presented_at is None:
            row.first_presented_at = reference_now
        row.last_presented_at = row.last_presented_at or reference_now

    await db.commit()
    return DashboardCoachFeedbackResponse(
        ok=True,
        advice_key=advice_key,
        event=event,
        status=row.status,
    )


async def attach_dashboard_coach_advice_to_snapshot(
    db: AsyncSession,
    *,
    snapshot: DecisionSnapshot,
    now: datetime | None = None,
) -> DashboardCoachAdvice | None:
    reference_now = now or datetime.now(timezone.utc)
    recent_cutoff = reference_now.replace(microsecond=0) - timedelta(days=ADVICE_LINK_WINDOW_DAYS)

    row = (
        await db.execute(
            select(DashboardCoachAdvice)
            .where(
                DashboardCoachAdvice.user_id == snapshot.user_id,
                DashboardCoachAdvice.status == "acted",
                DashboardCoachAdvice.decision_snapshot_id.is_(None),
                DashboardCoachAdvice.holding_id == snapshot.holding_id,
                or_(
                    DashboardCoachAdvice.thesis_id.is_(None),
                    DashboardCoachAdvice.thesis_id == snapshot.thesis_id,
                ),
                DashboardCoachAdvice.last_acted_at.is_not(None),
                DashboardCoachAdvice.last_acted_at >= recent_cutoff,
            )
            .order_by(DashboardCoachAdvice.last_acted_at.desc())
        )
    ).scalars().first()

    if row is None:
        return None

    row.decision_snapshot_id = snapshot.id
    row.updated_at = reference_now
    return row


async def sync_dashboard_coach_outcome_for_snapshot(
    db: AsyncSession,
    *,
    snapshot: DecisionSnapshot,
    now: datetime | None = None,
) -> None:
    advice_rows = (
        await db.execute(
            select(DashboardCoachAdvice).where(
                DashboardCoachAdvice.decision_snapshot_id == snapshot.id,
            )
        )
    ).scalars().all()

    if not advice_rows:
        return

    reference_now = now or datetime.now(timezone.utc)
    outcome = classify_snapshot_outcome(snapshot)
    for row in advice_rows:
        row.resolved_at = reference_now
        row.outcome_kind = outcome
        row.updated_at = reference_now
