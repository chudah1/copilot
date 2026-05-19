import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.onboarding_draft import OnboardingDraft
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.onboarding import (
    HoldingContextResponse,
    OnboardingStateResponse,
    OnboardingStatusResponse,
    OnboardingStepStatus,
    SynthesisRequest,
    SynthesisResponse,
)
from app.services.ai_thesis import synthesize_thesis_from_qa
from app.services.onboarding import coverage_pct, get_or_create_state, mark_onboarding_completed

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

CURRENT_THESIS_STATUSES = ["draft", "active", "needs_review"]


@router.get("/status", response_model=OnboardingStatusResponse)
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await get_or_create_state(db, current_user.id)
    if current_user.onboarding_completed_at is not None or state.onboarding_completed_at is not None:
        holdings_count_result = await db.execute(
            select(func.count()).select_from(Holding).where(Holding.user_id == current_user.id)
        )
        holdings_count = holdings_count_result.scalar() or 0

        theses_count_result = await db.execute(
            select(func.count()).select_from(Thesis).where(
                Thesis.user_id == current_user.id,
                Thesis.status.in_(CURRENT_THESIS_STATUSES),
            )
        )
        theses_count = theses_count_result.scalar() or 0

        return OnboardingStatusResponse(
            completed=True,
            current_step=None,
            steps={
                "import_holdings": OnboardingStepStatus(done=True, count=holdings_count),
                "write_first_thesis": OnboardingStepStatus(done=True, count=theses_count),
                "review_portfolio_health": OnboardingStepStatus(done=True),
            },
        )

    # Compute from live data
    holdings_count_result = await db.execute(
        select(func.count()).select_from(Holding).where(Holding.user_id == current_user.id)
    )
    holdings_count = holdings_count_result.scalar() or 0
    has_holdings = holdings_count > 0

    theses_count_result = await db.execute(
        select(func.count()).select_from(Thesis).where(
            Thesis.user_id == current_user.id,
            Thesis.status.in_(CURRENT_THESIS_STATUSES),
        )
    )
    theses_count = theses_count_result.scalar() or 0
    has_thesis = theses_count > 0

    all_done = has_holdings and has_thesis
    if all_done:
        completed_at = datetime.now(timezone.utc)
        await mark_onboarding_completed(db, user_id=current_user.id, completed_at=completed_at)
        await db.commit()

    if not has_holdings:
        current_step = "import_holdings"
    elif not has_thesis:
        current_step = "write_first_thesis"
    else:
        current_step = None

    return OnboardingStatusResponse(
        completed=all_done,
        current_step=current_step,
        steps={
            "import_holdings": OnboardingStepStatus(done=has_holdings, count=holdings_count),
            "write_first_thesis": OnboardingStepStatus(done=has_thesis, count=theses_count),
            "review_portfolio_health": OnboardingStepStatus(done=all_done),
        },
    )


class SuggestedHolding(BaseModel):
    id: str
    ticker: str
    name: str


class OnboardingBannerResponse(BaseModel):
    show: bool
    banner_type: str | None
    message: str | None
    holdings_count: int
    reasons_count: int
    suggested_holding: SuggestedHolding | None = None


@router.get("/banner", response_model=OnboardingBannerResponse)
async def onboarding_banner(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # If user completed onboarding (old flow), no banner
    if current_user.onboarding_completed_at is not None:
        return OnboardingBannerResponse(show=False, banner_type=None, message=None, holdings_count=0, reasons_count=0)

    state = await get_or_create_state(db, current_user.id)

    # If drip onboarding completed, no banner
    if state.onboarding_completed_at is not None:
        return OnboardingBannerResponse(show=False, banner_type=None, message=None, holdings_count=0, reasons_count=0)

    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = holdings_result.scalars().all()
    holdings_count = len(holdings)

    if holdings_count == 0:
        return OnboardingBannerResponse(show=False, banner_type=None, message=None, holdings_count=0, reasons_count=0)

    theses_result = await db.execute(
        select(Thesis).where(
            Thesis.user_id == current_user.id,
            Thesis.status.in_(CURRENT_THESIS_STATUSES),
        )
    )
    theses = theses_result.scalars().all()
    reasons_count = len(theses)
    thesis_holding_ids = {str(t.holding_id) for t in theses}

    now = datetime.now(timezone.utc)
    uncovered = [h for h in holdings if str(h.id) not in thesis_holding_ids]

    # Day 0: no reason written yet
    if state.first_reason_written_at is None:
        noun = "holding" if holdings_count == 1 else "holdings"
        message = f"You have {holdings_count} {noun}. Let's start with one — which matters most to you?"
        return OnboardingBannerResponse(
            show=True,
            banner_type="start_first_reason",
            message=message,
            holdings_count=holdings_count,
            reasons_count=reasons_count,
        )

    # Within 24h of first reason: monitoring confirmation (shown regardless of coverage)
    hours_since_first = (now - state.first_reason_written_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    if hours_since_first < 24:
        return OnboardingBannerResponse(
            show=True,
            banner_type="first_reason_monitoring",
            message="Your first reason is being monitored. Come back in a few days to see how it's holding up.",
            holdings_count=holdings_count,
            reasons_count=reasons_count,
        )

    # >50% covered — stop drip banner
    if reasons_count / holdings_count > 0.5:
        return OnboardingBannerResponse(show=False, banner_type=None, message=None, holdings_count=holdings_count, reasons_count=reasons_count)

    # Day 3+: suggest next holding
    if not uncovered:
        return OnboardingBannerResponse(show=False, banner_type=None, message=None, holdings_count=holdings_count, reasons_count=reasons_count)

    # Find best suggestion: earnings soonest, then highest value
    suggested: Holding | None = None
    earliest_earnings: datetime | None = None
    upcoming_window = now + timedelta(days=30)

    tickers = [h.ticker for h in uncovered]
    earnings_result = await db.execute(
        select(EarningsCalendar).where(
            EarningsCalendar.ticker.in_(tickers),
            EarningsCalendar.report_date >= now,
            EarningsCalendar.report_date <= upcoming_window,
        ).order_by(EarningsCalendar.report_date).limit(1)
    )
    next_earnings = earnings_result.scalar_one_or_none()
    if next_earnings is not None:
        suggested = next((h for h in uncovered if h.ticker == next_earnings.ticker), None)

    if suggested is None:
        # Fall back to highest value holding without a reason
        suggested = max(uncovered, key=lambda h: float(h.current_value or 0), default=uncovered[0])

    message = (
        f"You've got a reason for {reasons_count} of {holdings_count} holdings. "
        f"The ones without a reason are blind spots. Want to add one for {suggested.ticker}?"
    )
    return OnboardingBannerResponse(
        show=True,
        banner_type="add_more_reasons",
        message=message,
        holdings_count=holdings_count,
        reasons_count=reasons_count,
        suggested_holding=SuggestedHolding(
            id=str(suggested.id),
            ticker=suggested.ticker,
            name=suggested.name,
        ),
    )


# ---------------------------------------------------------------------------
# Wizard activation endpoints
# ---------------------------------------------------------------------------


@router.get("/state", response_model=OnboardingStateResponse)
async def wizard_state(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await get_or_create_state(db, current_user.id)
    if db.new:
        await db.commit()
    return OnboardingStateResponse(
        portfolio_connected=state.portfolio_connected_at is not None,
        drafts_generated_at=state.drafts_generated_at,
        drafts_reviewed_at=state.drafts_reviewed_at,
        wizard_skipped_at=state.wizard_skipped_at,
        wizard_completed_at=state.wizard_completed_at,
        reasons_written_count=state.reasons_written_count or 0,
    )


@router.post("/skip", status_code=status.HTTP_204_NO_CONTENT)
async def wizard_skip(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await get_or_create_state(db, current_user.id)
    if state.wizard_skipped_at is None:
        state.wizard_skipped_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/complete", status_code=status.HTTP_204_NO_CONTENT)
async def wizard_complete(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state = await get_or_create_state(db, current_user.id)
    now = datetime.now(timezone.utc)
    if state.wizard_completed_at is None:
        state.wizard_completed_at = now
    await db.commit()


@router.post("/synthesize", response_model=SynthesisResponse, status_code=status.HTTP_201_CREATED)
async def synthesize_thesis(
    body: SynthesisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding_result = await db.execute(
        select(Holding).where(Holding.id == body.holding_id, Holding.user_id == current_user.id)
    )
    holding = holding_result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    output = await synthesize_thesis_from_qa(
        ticker=holding.ticker,
        name=holding.name,
        question1=body.question1,
        answer1=body.answer1,
        question2=body.question2,
        answer2=body.answer2,
    )

    thesis = Thesis(
        holding_id=holding.id,
        user_id=current_user.id,
        status="draft",
        source="wizard",
        confidence="medium",
        why_own_it=output.why_own_it,
        must_remain_true=output.must_remain_true,
        what_would_change_my_mind=output.what_would_change_my_mind,
        ai_summary=output.ai_summary,
        interpretation=output.interpretation,
    )
    db.add(thesis)
    await db.flush()

    draft_result = await db.execute(
        select(OnboardingDraft).where(
            OnboardingDraft.holding_id == holding.id,
            OnboardingDraft.user_id == current_user.id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if draft is not None:
        draft.status = "reviewed"
        draft.thesis_id = thesis.id
        draft.updated_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    state = await get_or_create_state(db, current_user.id)
    state.reasons_written_count = (state.reasons_written_count or 0) + 1
    if state.first_reason_written_at is None:
        state.first_reason_written_at = now
    if state.drafts_reviewed_at is None:
        state.drafts_reviewed_at = now

    await db.commit()

    return SynthesisResponse(
        thesis_id=thesis.id,
        why_own_it=thesis.why_own_it,
        must_remain_true=thesis.must_remain_true or "",
        what_would_change_my_mind=thesis.what_would_change_my_mind or "",
        ai_summary=thesis.ai_summary or "",
    )


@router.get("/context/{holding_id}", response_model=HoldingContextResponse)
async def holding_context(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == current_user.id)
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    return HoldingContextResponse(
        holding_id=holding.id,
        ticker=holding.ticker,
        name=holding.name,
        sector=holding.sector,
        current_price=float(holding.current_price) if holding.current_price is not None else None,
        current_value=float(holding.current_value) if holding.current_value is not None else None,
        quantity=float(holding.quantity),
        average_cost_basis=float(holding.average_cost_basis),
    )
