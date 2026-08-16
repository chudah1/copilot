import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.limiter import limiter
from app.models.digest import Digest
from app.models.user import User
from app.schemas.digest import DigestResponse

router = APIRouter(prefix="/api/digests", tags=["digests"])


@router.get("", response_model=list[DigestResponse])
async def list_digests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Digest).where(Digest.user_id == user.id).order_by(Digest.period_end.desc()).limit(20))
    return result.scalars().all()


@router.post("/generate", response_model=DigestResponse)
@limiter.limit("4/hour")
async def generate_digest(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build a digest on demand from the last 7 days and persist it for in-app
    viewing (no email). Lets a user see the curated summary whenever they want,
    rather than waiting for the Sunday run."""
    from app.jobs.digest_builder import build_and_persist_user_digest

    now = datetime.now(timezone.utc)
    digest = await build_and_persist_user_digest(
        db,
        user,
        now=now,
        period_start=now - timedelta(days=7),
        period_end=now,
        send_email=False,      # in-app preview — don't email on every press
        update_streak=False,   # the weekly job owns the quiet-streak counter
    )
    if digest is None:
        raise HTTPException(status_code=400, detail="Add a holding with a reason before generating a digest")
    await db.commit()
    await db.refresh(digest)
    return digest


@router.get("/{digest_id}", response_model=DigestResponse)
async def get_digest(digest_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Digest).where(Digest.id == digest_id, Digest.user_id == user.id))
    digest = result.scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@router.post("/{digest_id}/review", response_model=DigestResponse)
async def review_digest(
    digest_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Digest).where(Digest.id == digest_id, Digest.user_id == user.id))
    digest = result.scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")

    if digest.reviewed_at is None:
        digest.reviewed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(digest)
    return digest
