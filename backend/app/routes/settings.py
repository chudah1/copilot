from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


class UserPreferences(BaseModel):
    digest_frequency: str = "weekly"
    notification_sensitivity: str = "all"


@router.get("", response_model=UserPreferences)
async def get_settings(user: User = Depends(get_current_user)):
    return UserPreferences(**user.preferences)


@router.put("", response_model=UserPreferences)
async def update_settings(body: UserPreferences, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.preferences = body.model_dump()
    await db.commit()
    return body
