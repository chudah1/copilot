from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.onboarding import OnboardingStatusResponse, OnboardingStepStatus

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
