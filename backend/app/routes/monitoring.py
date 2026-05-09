import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.monitoring_event import MonitoringEvent
from app.models.holding import Holding
from app.models.user import User
from app.schemas.monitoring_event import MonitoringEventResponse

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/holdings/{holding_id}/events", response_model=list[MonitoringEventResponse])
async def get_events_for_holding(holding_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MonitoringEvent).where(
            MonitoringEvent.holding_id == holding_id,
            MonitoringEvent.holding.has(user_id=user.id)
        ).order_by(MonitoringEvent.created_at.desc()).limit(50)
    )
    return result.scalars().all()
