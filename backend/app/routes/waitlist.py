import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.database import async_session
from app.limiter import limiter

logger = logging.getLogger(__name__)
MANIFESTO_URL = "https://penkeep.io/blog"

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("", status_code=201)
@limiter.limit("5/hour")
async def join_waitlist(request: Request, body: WaitlistRequest):
    inserted = False
    async with async_session() as db:
        try:
            result = await db.execute(
                text(
                    "INSERT INTO waitlist_entries (email, joined_at) "
                    "VALUES (:email, :joined_at) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"email": str(body.email), "joined_at": datetime.now(timezone.utc)},
            )
            await db.commit()
            inserted = result.rowcount > 0
        except Exception as exc:
            logger.warning("Waitlist insert failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Waitlist is temporarily unavailable. Please try again.",
            ) from exc

    if inserted:
        _send_confirmation(str(body.email))
    return {"ok": True}


def _send_confirmation(email: str) -> None:
    try:
        from app.config import settings
        if not settings.resend_api_key:
            return
        import resend
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": "penKeep <noreply@penkeep.io>",
            "to": email,
            "subject": "You're on the penKeep waitlist",
            "html": (
                "<p>Thanks for joining the penKeep waitlist.</p>"
                "<p>We'll email you when it's ready. In the meantime, "
                f"read the <a href='{MANIFESTO_URL}'>manifesto</a>.</p>"
                "<p style='color:#7a7268;font-size:13px'>— The penKeep team</p>"
            ),
        })
    except Exception as exc:
        logger.warning("Waitlist confirmation email failed: %s", exc)
