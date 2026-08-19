from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.services.password_reset import create_reset_token, validate_reset_token
from app.services.email import send_password_reset_email
from app.limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_kwargs(request: Request) -> dict[str, object]:
    secure = request.url.scheme == "https"
    # Browsers drop `SameSite=None` cookies unless `Secure` is also set.
    # For local HTTP development, use `Lax` so auth works on localhost/127.0.0.1.
    kwargs: dict[str, object] = dict(
        httponly=True, secure=secure, samesite="none" if secure else "lax"
    )

    # The backend runs on api.penkeep.io but the frontend + Edge middleware
    # live on penkeep.io / app.penkeep.io. Without an explicit Domain, the
    # cookie is scoped to api.penkeep.io only — invisible to the middleware
    # handling penkeep.io/dashboard, which then redirects a freshly-registered
    # user straight back to /login?from=/dashboard. Setting Domain to the
    # apex .penkeep.io makes the cookie shared across every subdomain we
    # deploy. Skipped for localhost since browsers reject Domain= there.
    host = request.url.hostname or ""
    if host.endswith(".penkeep.io") or host == "penkeep.io":
        kwargs["domain"] = ".penkeep.io"
    return kwargs


def _is_local_dev_request(request: Request) -> bool:
    return request.url.hostname in {"127.0.0.1", "localhost"}


def _safe_local_redirect(target: str | None) -> str:
    fallback = f"{settings.frontend_url.rstrip('/')}/dashboard"
    if not target:
        return fallback

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"}:
        return fallback
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return fallback
    return target


def _set_auth_cookies(
    request: Request,
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
) -> None:
    cookie_kwargs = _cookie_kwargs(request)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.jwt_access_token_expire_minutes * 60,
        **cookie_kwargs,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        **cookie_kwargs,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(request: Request, body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    if not settings.enable_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is currently closed. Join the waitlist and we'll email you access.",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    _set_auth_cookies(request, response, access_token=access_token, refresh_token=refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_seen_at = datetime.now(timezone.utc)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    await db.commit()

    _set_auth_cookies(request, response, access_token=access_token, refresh_token=refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token and body:
        refresh_token = body.refresh_token

    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    access_token = create_access_token(user_id)
    new_refresh_token = create_refresh_token(user_id)
    _set_auth_cookies(request, response, access_token=access_token, refresh_token=new_refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout")
async def logout(request: Request, response: Response):
    cookie_kwargs = _cookie_kwargs(request)
    response.delete_cookie(key="access_token", **cookie_kwargs)
    response.delete_cookie(key="refresh_token", **cookie_kwargs)
    return {"message": "Logged out successfully"}


@router.get("/dev-login")
async def dev_login(
    request: Request,
    email: str = Query(...),
    redirect: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not _is_local_dev_request(request):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    normalized_email = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=normalized_email, password_hash=hash_password("dev-login-only"))
        db.add(user)
        await db.commit()
        await db.refresh(user)

    user.last_seen_at = datetime.now(timezone.utc)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    response = RedirectResponse(url=_safe_local_redirect(redirect), status_code=status.HTTP_303_SEE_OTHER)
    _set_auth_cookies(request, response, access_token=access_token, refresh_token=refresh_token)
    await db.commit()
    return response


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email}


@router.post("/forgot-password")
@limiter.limit("3/10minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        raw_token = await create_reset_token(user.id, db)
        await send_password_reset_email(user.email, raw_token)
    # Always return 200 to avoid email enumeration
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    user_id = await validate_reset_token(body.token, db)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.password_hash = hash_password(body.new_password)
    # Single commit: token marked as used + password changed atomically
    await db.commit()
    return {"message": "Password has been reset."}
