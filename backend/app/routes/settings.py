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


def _normalize_preferences(preferences: dict | None) -> UserPreferences:
    raw = preferences or {}
    digest_frequency = raw.get("digest_frequency", "weekly")
    if digest_frequency not in {"weekly", "none"}:
        digest_frequency = "weekly"

    notification_sensitivity = raw.get("notification_sensitivity", "all")
    if notification_sensitivity not in {"all", "thesis_breaking_only"}:
        notification_sensitivity = "all"

    return UserPreferences(
        digest_frequency=digest_frequency,
        notification_sensitivity=notification_sensitivity,
    )


@router.get("", response_model=UserPreferences)
async def get_settings(user: User = Depends(get_current_user)):
    return _normalize_preferences(user.preferences)


@router.put("", response_model=UserPreferences)
async def update_settings(body: UserPreferences, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    normalized = _normalize_preferences(body.model_dump())
    user.preferences = normalized.model_dump()
    await db.commit()
    return normalized
