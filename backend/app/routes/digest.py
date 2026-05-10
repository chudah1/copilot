import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import get_current_user
from app.models.digest import Digest
from app.models.user import User
from app.schemas.digest import DigestResponse

router = APIRouter(prefix="/api/digests", tags=["digests"])


@router.get("", response_model=list[DigestResponse])
async def list_digests(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Digest).where(Digest.user_id == user.id).order_by(Digest.period_end.desc()).limit(20))
    return result.scalars().all()


@router.get("/{digest_id}", response_model=DigestResponse)
async def get_digest(digest_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Digest).where(Digest.id == digest_id, Digest.user_id == user.id))
    digest = result.scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest
