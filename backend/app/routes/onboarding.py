from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.earnings_calendar import EarningsCalendar
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.onboarding import OnboardingStatusResponse, OnboardingStepStatus
from app.services.onboarding import get_or_create_state, coverage_pct

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

CURRENT_THESIS_STATUSES = ["draft", "active", "needs_review"]


@router.get("/status", response_model=OnboardingStatusResponse)
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.onboarding_completed_at is not None:
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
        current_user.onboarding_completed_at = datetime.now(timezone.utc)
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
        ).order_by(EarningsCalendar.report_date)
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
