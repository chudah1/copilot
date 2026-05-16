from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/settings", tags=["settings"])

VALID_FREQUENCIES = {"weekly", "fortnightly", "monthly", "none"}
VALID_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
VALID_SENSITIVITIES = {"all", "thesis_breaking_only"}


class UserPreferences(BaseModel):
    digest_frequency: str = "weekly"
    digest_day: str = "sunday"
    digest_time: str = "17:00"
    earnings_alerts: bool = True
    quarterly_review_reminders: bool = True
    email_enabled: bool = True
    notification_sensitivity: str = "all"

    @field_validator("digest_frequency")
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        return v if v in VALID_FREQUENCIES else "weekly"

    @field_validator("digest_day")
    @classmethod
    def validate_day(cls, v: str) -> str:
        return v.lower() if v.lower() in VALID_DAYS else "sunday"

    @field_validator("digest_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"
        return "17:00"

    @field_validator("notification_sensitivity")
    @classmethod
    def validate_sensitivity(cls, v: str) -> str:
        return v if v in VALID_SENSITIVITIES else "all"


def get_user_prefs(user: User) -> UserPreferences:
    """Return normalized preferences for a user, applying defaults for missing keys."""
    raw = user.preferences or {}
    return UserPreferences(
        digest_frequency=raw.get("digest_frequency", "weekly"),
        digest_day=raw.get("digest_day", "sunday"),
        digest_time=raw.get("digest_time", "17:00"),
        earnings_alerts=bool(raw.get("earnings_alerts", True)),
        quarterly_review_reminders=bool(raw.get("quarterly_review_reminders", True)),
        email_enabled=bool(raw.get("email_enabled", True)),
        notification_sensitivity=raw.get("notification_sensitivity", "all"),
    )


@router.get("", response_model=UserPreferences)
async def get_settings(user: User = Depends(get_current_user)):
    return get_user_prefs(user)


@router.put("", response_model=UserPreferences)
async def update_settings(
    body: UserPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Merge into existing preferences to preserve any keys not in the schema
    existing = dict(user.preferences or {})
    existing.update(body.model_dump())
    user.preferences = existing
    await db.commit()
    return get_user_prefs(user)
