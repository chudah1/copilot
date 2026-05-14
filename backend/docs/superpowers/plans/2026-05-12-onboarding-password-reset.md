# Onboarding, Unthesised Holdings & Password Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend-driven onboarding status, an endpoint for holdings without theses, and password reset via email.

**Architecture:** Three independent features built as new routes/models. Onboarding is computed from live data (no separate state table). Password reset uses a `password_reset_tokens` table with hashed tokens and 1-hour expiry. Unthesised holdings is a focused query endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, bcrypt, Resend email, existing JWT/auth infrastructure.

---

### Task 1: Password Reset Token Model

**Files:**
- Create: `app/models/password_reset_token.py`
- Modify: `app/main.py:9` (add model import for auto-create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_password_reset.py`:

```python
from app.models.password_reset_token import PasswordResetToken


def test_password_reset_token_model_exists():
    assert PasswordResetToken.__tablename__ == "password_reset_tokens"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py::test_password_reset_token_model_exists -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the model**

Create `app/models/password_reset_token.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, UUIDType


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Register the model import in `app/main.py`**

Add to the existing model imports line (line 9):

```python
from app.models import user, broker_connection, holding, thesis, monitoring_event, digest, password_reset_token  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py::test_password_reset_token_model_exists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/models/password_reset_token.py app/main.py tests/test_password_reset.py
git commit -m "feat: add PasswordResetToken model"
```

---

### Task 2: Password Reset Service Layer

**Files:**
- Create: `app/services/password_reset.py`
- Modify: `app/services/email.py` (add `send_password_reset_email`)
- Test: `tests/test_password_reset.py` (add service tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_password_reset.py`:

```python
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.password_reset_token import PasswordResetToken
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py -v -k "not model_exists"`
Expected: FAIL with `ModuleNotFoundError` for `app.services.password_reset`

- [ ] **Step 3: Write the password reset service**

Create `app/services/password_reset.py`:

```python
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken

TOKEN_EXPIRY_HOURS = 1


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def create_reset_token(user_id: uuid.UUID, db: AsyncSession) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

    reset_token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    await db.commit()
    return raw_token


async def validate_reset_token(raw_token: str, db: AsyncSession) -> uuid.UUID | None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token_row = result.scalar_one_or_none()
    if token_row is None:
        return None

    token_row.used_at = datetime.now(timezone.utc)
    await db.commit()
    return token_row.user_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py -v`
Expected: All PASS

- [ ] **Step 5: Add `send_password_reset_email` to `app/services/email.py`**

Append to `app/services/email.py`:

```python
async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    if not settings.resend_api_key:
        logger.warning("No Resend API key configured — skipping password reset email")
        return False
    resend.api_key = settings.resend_api_key
    html = (
        "<h2>Reset your password</h2>"
        "<p>Use this code to reset your Copilot Investor password. It expires in 1 hour.</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:2px'>{reset_token}</p>"
        "<p>If you didn't request this, ignore this email.</p>"
    )
    try:
        resend.Emails.send({
            "from": "Copilot Investor <noreply@copilotinvestor.com>",
            "to": [to_email],
            "subject": "Reset your password",
            "html": html,
        })
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return False
```

- [ ] **Step 6: Commit**

```bash
git add app/services/password_reset.py app/services/email.py tests/test_password_reset.py
git commit -m "feat: add password reset service with token creation and validation"
```

---

### Task 3: Password Reset Endpoints

**Files:**
- Modify: `app/routes/auth.py` (add forgot-password and reset-password endpoints)
- Modify: `app/schemas/auth.py` (add request schemas)
- Test: `tests/test_password_reset.py` (add endpoint tests)

- [ ] **Step 1: Add schemas to `app/schemas/auth.py`**

Append to `app/schemas/auth.py`:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
```

- [ ] **Step 2: Write the failing endpoint tests**

Append to `tests/test_password_reset.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py -v -k "forgot or reset_password"`
Expected: FAIL with 404 (endpoints don't exist yet)

- [ ] **Step 4: Add the endpoints to `app/routes/auth.py`**

Add these imports at the top of `app/routes/auth.py`:

```python
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.services.password_reset import create_reset_token, validate_reset_token
from app.services.email import send_password_reset_email
```

Add these endpoints to `app/routes/auth.py`:

```python
@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
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
    await db.commit()
    return {"message": "Password has been reset."}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_password_reset.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add app/routes/auth.py app/schemas/auth.py tests/test_password_reset.py
git commit -m "feat: add forgot-password and reset-password endpoints"
```

---

### Task 4: Unthesised Holdings Endpoint

**Files:**
- Modify: `app/routes/portfolio.py` (add endpoint)
- Modify: `app/schemas/holding.py` (add response schema if needed — reuse `HoldingResponse`)
- Create: `tests/test_unthesised.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_unthesised.py`:

```python
async def test_unthesised_returns_holdings_without_active_thesis(client, auth_headers, db, test_user):
    # Create two holdings
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)
    h2 = await client.post("/api/portfolio/holdings", json={
        "ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300,
    }, headers=auth_headers)

    # Create thesis only for AAPL
    await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Ecosystem and margins.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    tickers = [h["ticker"] for h in response.json()]
    assert tickers == ["MSFT"]


async def test_unthesised_returns_empty_when_all_have_theses(client, auth_headers, db, test_user):
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_unthesised_excludes_invalidated_theses(client, auth_headers, db, test_user):
    h1 = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    create_resp = await client.post("/api/theses", json={
        "holding_id": h1.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Old thesis.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    # Invalidate it
    await client.post(
        f"/api/theses/{create_resp.json()['id']}/invalidate",
        json={"reason": "No longer valid"},
        headers=auth_headers,
    )

    response = await client.get("/api/portfolio/holdings/unthesised", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["ticker"] == "AAPL"


async def test_unthesised_requires_auth(client):
    response = await client.get("/api/portfolio/holdings/unthesised")
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_unthesised.py -v`
Expected: FAIL with 404 or 405

- [ ] **Step 3: Add the endpoint to `app/routes/portfolio.py`**

Add this endpoint **before** the `@router.post("/holdings", ...)` route (important: path ordering — `/holdings/unthesised` must come before `/{param}` style routes, and after the existing `/holdings` GET):

```python
@router.get("/holdings/unthesised", response_model=list[HoldingResponse])
async def list_unthesised_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = holdings_result.scalars().all()

    if not holdings:
        return []

    holding_ids = [h.id for h in holdings]
    theses_result = await db.execute(
        select(Thesis.holding_id)
        .where(
            Thesis.holding_id.in_(holding_ids),
            Thesis.user_id == current_user.id,
            Thesis.status.in_(["draft", "active", "needs_review"]),
        )
        .distinct()
    )
    holdings_with_thesis = {row[0] for row in theses_result.all()}

    unthesised = [h for h in holdings if h.id not in holdings_with_thesis]
    unthesised.sort(key=_holding_value, reverse=True)
    return unthesised
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_unthesised.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes/portfolio.py tests/test_unthesised.py
git commit -m "feat: add GET /holdings/unthesised endpoint"
```

---

### Task 5: Onboarding Status Endpoint

**Files:**
- Modify: `app/models/user.py` (add `onboarding_completed_at` field)
- Create: `app/routes/onboarding.py`
- Create: `app/schemas/onboarding.py`
- Modify: `app/main.py` (register new router)
- Create: `tests/test_onboarding.py`

- [ ] **Step 1: Add `onboarding_completed_at` to User model**

In `app/models/user.py`, add after the `created_at` field:

```python
onboarding_completed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True, default=None
)
```

- [ ] **Step 2: Create the onboarding schema**

Create `app/schemas/onboarding.py`:

```python
from pydantic import BaseModel


class OnboardingStepStatus(BaseModel):
    done: bool
    count: int | None = None


class OnboardingStatusResponse(BaseModel):
    completed: bool
    current_step: str | None
    steps: dict[str, OnboardingStepStatus]
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_onboarding.py`:

```python
async def test_onboarding_status_new_user(client, auth_headers, test_user):
    response = await client.get("/api/onboarding/status", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["completed"] is False
    assert data["current_step"] == "import_holdings"
    assert data["steps"]["import_holdings"]["done"] is False
    assert data["steps"]["import_holdings"]["count"] == 0
    assert data["steps"]["write_first_thesis"]["done"] is False
    assert data["steps"]["write_first_thesis"]["count"] == 0


async def test_onboarding_after_adding_holdings(client, auth_headers, test_user):
    await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is False
    assert data["current_step"] == "write_first_thesis"
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["import_holdings"]["count"] == 1
    assert data["steps"]["write_first_thesis"]["done"] is False


async def test_onboarding_completes_after_first_thesis(client, auth_headers, test_user, db):
    h = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder with durable ecosystem.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is True
    assert data["current_step"] is None
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["write_first_thesis"]["done"] is True
    assert data["steps"]["write_first_thesis"]["count"] == 1
    assert data["steps"]["review_portfolio_health"]["done"] is True


async def test_onboarding_already_completed_user_stays_completed(client, auth_headers, test_user, db):
    h = await client.post("/api/portfolio/holdings", json={
        "ticker": "AAPL", "name": "Apple", "quantity": 10, "average_cost_basis": 150,
    }, headers=auth_headers)

    await client.post("/api/theses", json={
        "holding_id": h.json()["id"],
        "status": "active",
        "thesis_kind": "company",
        "why_own_it": "Quality compounder.",
        "confidence": "high",
        "review_cadence_days": 7,
        "source": "user",
    }, headers=auth_headers)

    # First call completes onboarding
    await client.get("/api/onboarding/status", headers=auth_headers)

    # Second call should still be completed (reads from user field)
    response = await client.get("/api/onboarding/status", headers=auth_headers)
    data = response.json()
    assert data["completed"] is True


async def test_onboarding_requires_auth(client):
    response = await client.get("/api/onboarding/status")
    assert response.status_code == 403
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_onboarding.py -v`
Expected: FAIL with 404

- [ ] **Step 5: Create the onboarding route**

Create `app/routes/onboarding.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.onboarding import OnboardingStatusResponse, OnboardingStepStatus

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

CURRENT_THESIS_STATUSES = ["draft", "active", "needs_review"]


@router.get("/status", response_model=OnboardingStatusResponse)
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.onboarding_completed_at is not None:
        holdings_count_result = await db.execute(
            select(func.count()).select_from(Holding).where(Holding.user_id == current_user.id)
        )
        holdings_count = holdings_count_result.scalar() or 0

        theses_count_result = await db.execute(
            select(func.count()).select_from(Thesis).where(
                Thesis.user_id == current_user.id,
                Thesis.status.in_(CURRENT_THESIS_STATUSES),
            )
        )
        theses_count = theses_count_result.scalar() or 0

        return OnboardingStatusResponse(
            completed=True,
            current_step=None,
            steps={
                "import_holdings": OnboardingStepStatus(done=True, count=holdings_count),
                "write_first_thesis": OnboardingStepStatus(done=True, count=theses_count),
                "review_portfolio_health": OnboardingStepStatus(done=True),
            },
        )

    # Compute from live data
    holdings_count_result = await db.execute(
        select(func.count()).select_from(Holding).where(Holding.user_id == current_user.id)
    )
    holdings_count = holdings_count_result.scalar() or 0
    has_holdings = holdings_count > 0

    theses_count_result = await db.execute(
        select(func.count()).select_from(Thesis).where(
            Thesis.user_id == current_user.id,
            Thesis.status.in_(CURRENT_THESIS_STATUSES),
        )
    )
    theses_count = theses_count_result.scalar() or 0
    has_thesis = theses_count > 0

    all_done = has_holdings and has_thesis
    if all_done:
        current_user.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()

    if not has_holdings:
        current_step = "import_holdings"
    elif not has_thesis:
        current_step = "write_first_thesis"
    else:
        current_step = None

    return OnboardingStatusResponse(
        completed=all_done,
        current_step=current_step,
        steps={
            "import_holdings": OnboardingStepStatus(done=has_holdings, count=holdings_count),
            "write_first_thesis": OnboardingStepStatus(done=has_thesis, count=theses_count),
            "review_portfolio_health": OnboardingStepStatus(done=all_done),
        },
    )
```

- [ ] **Step 6: Register the router in `app/main.py`**

Add after the digest router import:

```python
from app.routes.onboarding import router as onboarding_router
app.include_router(onboarding_router)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest tests/test_onboarding.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add app/models/user.py app/schemas/onboarding.py app/routes/onboarding.py app/main.py tests/test_onboarding.py
git commit -m "feat: add onboarding status endpoint with computed step progression"
```

---

### Task 6: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `cd /Users/cyakung/Projects/copilot_investor/backend && python -m pytest -v`
Expected: All existing + new tests PASS

- [ ] **Step 2: Fix any regressions**

If any existing tests fail due to the new `onboarding_completed_at` column or model import changes, fix them.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve test regressions from onboarding changes"
```
