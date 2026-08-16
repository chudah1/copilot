from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim_review import ClaimReview
from app.models.holding import Holding
from app.models.onboarding_draft import OnboardingDraft
from app.models.open_loop_dismissal import OpenLoopDismissal
from app.models.quarterly_review_response import QuarterlyReviewResponse
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.dashboard import DashboardOpenLoopDismissedResponse, DashboardOpenLoopResponse
from app.services.case_state import classify_case_quality
from app.services.claim_review import compute_check_in

ACTIVE_THESIS_STATUSES = ("draft", "active", "needs_review")
DEFAULT_DISMISS_DAYS = 7


@dataclass
class _OpenLoop:
    loop_key: str
    loop_type: str
    holding: Holding
    thesis_id: uuid.UUID | None
    title: str
    detail: str
    opened_at: datetime
    priority: int
    cta_label: str
    cta_href: str


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _age_in_days(value: datetime, *, now: datetime) -> int:
    return max((_as_utc(now) - _as_utc(value)).days, 0)


def _sort_key(loop: _OpenLoop) -> tuple[int, float, str]:
    return (loop.priority, -_as_utc(loop.opened_at).timestamp(), loop.holding.ticker)


def _serialize_loop(loop: _OpenLoop, *, now: datetime) -> DashboardOpenLoopResponse:
    return DashboardOpenLoopResponse(
        loop_key=loop.loop_key,
        loop_type=loop.loop_type,
        holding_id=loop.holding.id,
        thesis_id=loop.thesis_id,
        ticker=loop.holding.ticker,
        name=loop.holding.name,
        title=loop.title,
        detail=loop.detail,
        opened_at=loop.opened_at,
        age_days=_age_in_days(loop.opened_at, now=now),
        priority=loop.priority,
        cta_label=loop.cta_label,
        cta_href=loop.cta_href,
    )


async def _load_current_theses(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Thesis]:
    if not holding_ids:
        return {}

    theses_result = await db.execute(
        select(Thesis)
        .where(
            Thesis.user_id == user_id,
            Thesis.holding_id.in_(holding_ids),
            Thesis.status.in_(ACTIVE_THESIS_STATUSES),
        )
        .order_by(Thesis.created_at.desc())
    )
    theses_by_holding: dict[uuid.UUID, Thesis] = {}
    for thesis in theses_result.scalars().all():
        theses_by_holding.setdefault(thesis.holding_id, thesis)
    return theses_by_holding


async def _load_onboarding_drafts(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, OnboardingDraft]:
    rows = await db.execute(
        select(OnboardingDraft)
        .where(OnboardingDraft.user_id == user_id)
        .order_by(OnboardingDraft.updated_at.desc(), OnboardingDraft.created_at.desc())
    )
    drafts_by_holding: dict[uuid.UUID, OnboardingDraft] = {}
    for draft in rows.scalars().all():
        drafts_by_holding.setdefault(draft.holding_id, draft)
    return drafts_by_holding


async def _load_latest_quarterly_responses(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, QuarterlyReviewResponse]:
    rows = await db.execute(
        select(QuarterlyReviewResponse, Thesis)
        .join(Thesis, Thesis.id == QuarterlyReviewResponse.thesis_id)
        .where(Thesis.user_id == user_id)
        .order_by(QuarterlyReviewResponse.created_at.desc())
    )
    latest_by_thesis: dict[uuid.UUID, QuarterlyReviewResponse] = {}
    for response, thesis in rows.all():
        latest_by_thesis.setdefault(thesis.id, response)
    return latest_by_thesis


async def _load_latest_claim_review_by_claim(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
) -> dict[uuid.UUID | None, ClaimReview]:
    rows = await db.execute(
        select(ClaimReview)
        .where(ClaimReview.thesis_id == thesis_id)
        .order_by(ClaimReview.created_at.asc())
    )
    latest: dict[uuid.UUID | None, ClaimReview] = {}
    for review in rows.scalars().all():
        latest[review.claim_id] = review
    return latest


async def _claim_review_loops(
    db: AsyncSession,
    *,
    holding: Holding,
    thesis: Thesis,
) -> list[_OpenLoop]:
    states = await compute_check_in(db, thesis)
    latest_reviews = await _load_latest_claim_review_by_claim(db, thesis_id=thesis.id)
    loops: list[_OpenLoop] = []

    for state in states:
        if not state.needs_review or not state.threatens_events:
            continue

        latest_event = max(state.threatens_events, key=lambda event: _as_utc(event.created_at or datetime.now(timezone.utc)))
        oldest_event = min(state.threatens_events, key=lambda event: _as_utc(event.created_at or datetime.now(timezone.utc)))
        review = latest_reviews.get(state.claim_id)
        claim_key = str(state.claim_id) if state.claim_id is not None else "general"
        latest_event_id = str(latest_event.id)
        latest_review_at = review.created_at if review and review.created_at else None
        opened_at = oldest_event.created_at or latest_event.created_at or datetime.now(timezone.utc)
        loop_key = f"claim_review:{thesis.id}:{claim_key}:{latest_event_id}"
        label = state.label if state.claim_id is not None else "General evidence"
        title = f"{holding.ticker} needs a call on {label.lower()}."
        detail = state.needs_review_reason
        if latest_review_at is not None:
            detail = f"{detail} Last claim review was recorded before this evidence landed."

        loops.append(
            _OpenLoop(
                loop_key=loop_key,
                loop_type="claim_review",
                holding=holding,
                thesis_id=thesis.id,
                title=title,
                detail=detail,
                opened_at=_as_utc(opened_at),
                priority=0,
                cta_label="Finish claim review",
                cta_href=f"/dashboard/positions/{holding.ticker}?tab=monitoring",
            )
        )
    return loops


def _case_quality_loops(*, holding: Holding, thesis: Thesis, now: datetime) -> list[_OpenLoop]:
    case_quality = classify_case_quality(thesis, now=now)
    loops: list[_OpenLoop] = []
    thesis_updated_at = _as_utc(thesis.updated_at or thesis.created_at or now)

    if case_quality.kind == "weak":
        loop_key = f"weak_thesis:{thesis.id}:{int(thesis_updated_at.timestamp())}"
        loops.append(
            _OpenLoop(
                loop_key=loop_key,
                loop_type="weak_thesis",
                holding=holding,
                thesis_id=thesis.id,
                title=f"{holding.ticker} still needs a clearer written case.",
                detail="The current case is too vague, ambiguous, or missing the rules that would tell future-you what changed.",
                opened_at=thesis_updated_at,
                priority=2,
                cta_label="Tighten thesis",
                cta_href=f"/dashboard/positions/{holding.ticker}",
            )
        )

    review_pressure = case_quality.review_pressure
    if case_quality.kind == "review_overdue" and review_pressure is not None:
        opened_at = thesis_updated_at + timedelta(days=review_pressure.review_threshold)
        loop_key = f"review_overdue:{thesis.id}:{int(opened_at.timestamp())}"
        loops.append(
            _OpenLoop(
                loop_key=loop_key,
                loop_type="review_overdue",
                holding=holding,
                thesis_id=thesis.id,
                title=f"{holding.ticker} is overdue for a fresh read.",
                detail=f"This case is {review_pressure.days_old} days old and has drifted past its review cadence.",
                opened_at=opened_at,
                priority=3,
                cta_label="Decide if it still holds",
                cta_href=f"/dashboard/positions/{holding.ticker}?tab=decisions",
            )
        )

    return loops


def _quarterly_review_loop(
    *,
    holding: Holding,
    thesis: Thesis,
    response: QuarterlyReviewResponse | None,
) -> _OpenLoop | None:
    if response is None:
        return None
    if response.response not in {"not_sure", "no"}:
        return None
    if thesis.status != "needs_review":
        return None

    response_at = _as_utc(response.created_at)
    loop_key = f"quarterly_unsure:{response.id}:{int(response_at.timestamp())}"
    return _OpenLoop(
        loop_key=loop_key,
        loop_type="quarterly_unsure",
        holding=holding,
        thesis_id=thesis.id,
        title=f"{holding.ticker} still has an unresolved quarterly call.",
        detail="You said you were not sure you would buy this today. The written case still has not been closed out.",
        opened_at=response_at,
        priority=1,
        cta_label="Resolve quarterly call",
        cta_href=f"/dashboard/positions/{holding.ticker}?tab=decisions",
    )


def _draft_review_loop(
    *,
    holding: Holding,
    draft: OnboardingDraft | None,
) -> _OpenLoop | None:
    if draft is None or draft.status != "ready":
        return None

    updated_at = _as_utc(draft.updated_at or draft.created_at or datetime.now(timezone.utc))
    loop_key = f"draft_review:{draft.id}:{int(updated_at.timestamp())}"
    return _OpenLoop(
        loop_key=loop_key,
        loop_type="draft_unreviewed",
        holding=holding,
        thesis_id=draft.thesis_id,
        title=f"{holding.ticker} has an AI draft waiting for review.",
        detail="Monitoring should not take over until you confirm, edit, or dismiss the draft in your own words.",
        opened_at=updated_at,
        priority=4,
        cta_label="Review draft",
        cta_href="/onboarding/review-drafts",
    )


async def list_open_loops(
    db: AsyncSession,
    *,
    user: User,
    holding_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> list[DashboardOpenLoopResponse]:
    reference_now = now or datetime.now(timezone.utc)
    holdings_query = select(Holding).where(Holding.user_id == user.id)
    if holding_id is not None:
        holdings_query = holdings_query.where(Holding.id == holding_id)
    holdings_result = await db.execute(
        holdings_query.order_by(Holding.current_value.desc().nulls_last(), Holding.ticker.asc())
    )
    holdings = list(holdings_result.scalars().all())
    holding_ids = [holding.id for holding in holdings]
    theses_by_holding = await _load_current_theses(db, user_id=user.id, holding_ids=holding_ids)
    drafts_by_holding = await _load_onboarding_drafts(db, user_id=user.id)
    quarterly_by_thesis = await _load_latest_quarterly_responses(db, user_id=user.id)

    loops: list[_OpenLoop] = []
    for holding in holdings:
        draft_loop = _draft_review_loop(holding=holding, draft=drafts_by_holding.get(holding.id))
        if draft_loop is not None:
            loops.append(draft_loop)

        thesis = theses_by_holding.get(holding.id)
        if thesis is None:
            continue

        loops.extend(_case_quality_loops(holding=holding, thesis=thesis, now=reference_now))
        loops.extend(await _claim_review_loops(db, holding=holding, thesis=thesis))

        quarterly_loop = _quarterly_review_loop(
            holding=holding,
            thesis=thesis,
            response=quarterly_by_thesis.get(thesis.id),
        )
        if quarterly_loop is not None:
            loops.append(quarterly_loop)

    if not loops:
        return []

    dismissal_rows = (
        await db.execute(
            select(OpenLoopDismissal).where(
                OpenLoopDismissal.user_id == user.id,
                OpenLoopDismissal.loop_key.in_([loop.loop_key for loop in loops]),
                OpenLoopDismissal.dismissed_until > reference_now,
            )
        )
    ).scalars().all()
    dismissed = {row.loop_key for row in dismissal_rows}

    visible_loops = [loop for loop in loops if loop.loop_key not in dismissed]
    visible_loops.sort(key=_sort_key)
    return [_serialize_loop(loop, now=reference_now) for loop in visible_loops]


async def dismiss_open_loop(
    db: AsyncSession,
    *,
    user: User,
    loop_key: str,
    dismiss_for_days: int = DEFAULT_DISMISS_DAYS,
    now: datetime | None = None,
) -> DashboardOpenLoopDismissedResponse:
    reference_now = now or datetime.now(timezone.utc)
    dismissed_until = reference_now + timedelta(days=max(dismiss_for_days, 1))

    existing = (
        await db.execute(
            select(OpenLoopDismissal).where(
                OpenLoopDismissal.user_id == user.id,
                OpenLoopDismissal.loop_key == loop_key,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = OpenLoopDismissal(
            user_id=user.id,
            loop_key=loop_key,
            dismissed_until=dismissed_until,
            updated_at=reference_now,
        )
        db.add(existing)
    else:
        existing.dismissed_until = dismissed_until
        existing.updated_at = reference_now

    await db.commit()
    return DashboardOpenLoopDismissedResponse(
        ok=True,
        loop_key=loop_key,
        dismissed_until=dismissed_until,
    )
