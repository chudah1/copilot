import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.onboarding_state import OnboardingState


async def get_or_create_state(db: AsyncSession, user_id: uuid.UUID) -> OnboardingState:
    result = await db.execute(
        select(OnboardingState).where(OnboardingState.user_id == user_id)
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = OnboardingState(user_id=user_id)
        db.add(state)
        await db.flush()
    return state


async def mark_portfolio_connected(db: AsyncSession, user_id: uuid.UUID) -> None:
    state = await get_or_create_state(db, user_id)
    if state.portfolio_connected_at is None:
        state.portfolio_connected_at = datetime.now(timezone.utc)


async def mark_reason_written(db: AsyncSession, user_id: uuid.UUID) -> None:
    state = await get_or_create_state(db, user_id)
    state.reasons_written_count = (state.reasons_written_count or 0) + 1
    if state.first_reason_written_at is None:
        state.first_reason_written_at = datetime.now(timezone.utc)


async def mark_digest_received(db: AsyncSession, user_id: uuid.UUID) -> None:
    state = await get_or_create_state(db, user_id)
    if state.first_digest_received_at is None:
        state.first_digest_received_at = datetime.now(timezone.utc)
        state.onboarding_completed_at = datetime.now(timezone.utc)


def is_onboarding_complete(state: OnboardingState, holdings_count: int) -> bool:
    if state.onboarding_completed_at is not None:
        return True
    if holdings_count == 0:
        return False
    return (state.reasons_written_count or 0) >= holdings_count


def coverage_pct(state: OnboardingState, holdings_count: int) -> float:
    if holdings_count == 0:
        return 100.0
    return (state.reasons_written_count or 0) / holdings_count * 100.0
