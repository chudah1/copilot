from app.models.password_reset_token import PasswordResetToken


def test_password_reset_token_model_exists():
    assert PasswordResetToken.__tablename__ == "password_reset_tokens"


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


async def test_forgot_password_sends_email_for_existing_user(client, db):
    from app.services.auth import hash_password
    user = User(email="forgot@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()

    with patch("app.routes.auth.send_password_reset_email", new_callable=AsyncMock, return_value=True) as mock_send:
        response = await client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})

    assert response.status_code == 200
    assert response.json()["message"] == "If that email exists, a reset link has been sent."
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "forgot@example.com"


async def test_forgot_password_returns_200_for_nonexistent_email(client):
    response = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert response.status_code == 200
    assert response.json()["message"] == "If that email exists, a reset link has been sent."


async def test_reset_password_changes_password(client, db):
    from app.services.auth import hash_password, verify_password
    from app.services.password_reset import create_reset_token

    user = User(email="resetpw@example.com", password_hash=hash_password("oldpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)

    response = await client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "newpass456",
    })
    assert response.status_code == 200

    await db.refresh(user)
    assert verify_password("newpass456", user.password_hash)


async def test_reset_password_rejects_invalid_token(client):
    response = await client.post("/api/auth/reset-password", json={
        "token": "bogus-token",
        "new_password": "newpass456",
    })
    assert response.status_code == 400
    assert "Invalid or expired" in response.json()["detail"]


async def test_new_reset_token_invalidates_old_ones(db):
    user = User(email="multi@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    first_token = await create_reset_token(user.id, db)
    second_token = await create_reset_token(user.id, db)

    # First token should be invalidated
    found = await validate_reset_token(first_token, db)
    assert found is None

    # Second token should still work
    found = await validate_reset_token(second_token, db)
    assert found == user.id


async def test_reset_password_rejects_short_password(client, db):
    user = User(email="short@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    raw_token = await create_reset_token(user.id, db)
    response = await client.post("/api/auth/reset-password", json={
        "token": raw_token,
        "new_password": "short",
    })
    assert response.status_code == 422


async def test_register_rejects_short_password(client):
    response = await client.post("/api/auth/register", json={
        "email": "short@example.com",
        "password": "short",
    })
    assert response.status_code == 422
