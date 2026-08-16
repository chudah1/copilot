import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCommandCenterResponse,
    DashboardCoachFeedbackRequest,
    DashboardCoachFeedbackResponse,
    DashboardCoachMemoryResponse,
    DashboardOpenLoopDismissRequest,
    DashboardOpenLoopDismissedResponse,
    DashboardOpenLoopResponse,
    DashboardWorkspaceResponse,
)
from app.services.dashboard_command_center import build_dashboard_command_center
from app.services.dashboard_coach import get_dashboard_coach_memory, record_dashboard_coach_feedback
from app.services.dashboard_workspace import build_dashboard_workspace
from app.services.open_loops import dismiss_open_loop, list_open_loops

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/workspace", response_model=DashboardWorkspaceResponse)
async def get_dashboard_workspace(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_dashboard_workspace(db, user=current_user)


@router.get("/command-center", response_model=DashboardCommandCenterResponse)
async def get_dashboard_command_center(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await build_dashboard_command_center(db, user=current_user)


@router.get("/open-loops", response_model=list[DashboardOpenLoopResponse])
async def get_open_loops(
    holding_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_open_loops(db, user=current_user, holding_id=holding_id)


@router.get("/coach-memory", response_model=DashboardCoachMemoryResponse)
async def get_dashboard_coach_memory_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_dashboard_coach_memory(db, user_id=current_user.id)


@router.post("/coach-feedback", response_model=DashboardCoachFeedbackResponse)
async def post_dashboard_coach_feedback(
    body: DashboardCoachFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await record_dashboard_coach_feedback(
        db,
        user_id=current_user.id,
        advice_key=body.advice_key,
        mode=body.mode,
        event=body.event,
        holding_id=body.holding_id,
        thesis_id=body.thesis_id,
        loop_key=body.loop_key,
        pattern_kind=body.pattern_kind,
        action_label=body.action_label,
    )


@router.post("/open-loops/dismiss", response_model=DashboardOpenLoopDismissedResponse)
async def dismiss_dashboard_open_loop(
    body: DashboardOpenLoopDismissRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await dismiss_open_loop(
        db,
        user=current_user,
        loop_key=body.loop_key,
        dismiss_for_days=body.dismiss_for_days,
    )
