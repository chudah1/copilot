from app.models.password_reset_token import PasswordResetToken


def test_password_reset_token_model_exists():
    assert PasswordResetToken.__tablename__ == "password_reset_tokens"


import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.user import User
from app.services.auth import hash_password
from app.services.password_reset import create_reset_token, validate_reset_token


async def test_create_reset_token_returns_raw_token_and_stores_hash(db):
    user = User(email="reset@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)

    assert isinstance(raw_token, str)
    assert len(raw_token) >= 32

    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    stored = result.scalar_one()
    assert stored.token_hash != raw_token  # stored hash, not plaintext
    assert stored.expires_at > datetime.now(timezone.utc)
    assert stored.used_at is None


async def test_validate_reset_token_succeeds_with_valid_token(db):
    user = User(email="valid@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)
    found_user_id = await validate_reset_token(raw_token, db)
    assert found_user_id == user.id


async def test_validate_reset_token_rejects_expired_token(db):
    user = User(email="expired@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)

    # Manually expire it
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    token_row = result.scalar_one()
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    found_user_id = await validate_reset_token(raw_token, db)
    assert found_user_id is None


async def test_validate_reset_token_rejects_already_used_token(db):
    user = User(email="used@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)

    # Use it once
    found_user_id = await validate_reset_token(raw_token, db)
    assert found_user_id == user.id

    # Second use should fail
    found_user_id = await validate_reset_token(raw_token, db)
    assert found_user_id is None


async def test_validate_reset_token_rejects_wrong_token(db):
    user = User(email="wrong@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await create_reset_token(user.id, db)
    found_user_id = await validate_reset_token("completely-wrong-token", db)
    assert found_user_id is None
