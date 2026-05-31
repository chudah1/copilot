"""Tests for the on-demand first digest — the curated summary must reach a new
user in their first session, not days later on the Sunday job."""
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.jobs.digest_builder import build_first_digest_for_user
from app.models.digest import Digest
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.services.auth import hash_password

_DIGEST = "app.jobs.digest_builder"


async def _seed_user_with_position(db, email="firstdigest@example.com"):
    user = User(email=email, password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()
    holding = Holding(user_id=user.id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100, current_value=1500)
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=user.id, holding_id=holding.id, status="active", thesis_kind="company",
        why_own_it="Apple remains a quality compounder with durable services.",
        confidence="high", review_cadence_days=7, source="user",
    ))
    await db.commit()
    return user


async def test_first_digest_built_and_emailed(db, job_session_factory):
    user = await _seed_user_with_position(db)

    with patch(f"{_DIGEST}.async_session", job_session_factory), patch(
        f"{_DIGEST}.send_digest_email", new_callable=AsyncMock, return_value=True
    ) as send_mock:
        await build_first_digest_for_user(user.id)

    digests = (await db.execute(select(Digest).where(Digest.user_id == user.id))).scalars().all()
    assert len(digests) == 1
    assert digests[0].status == "sent"
    assert digests[0].content["html"]
    send_mock.assert_awaited_once()


async def test_first_digest_is_idempotent(db, job_session_factory):
    user = await _seed_user_with_position(db)

    with patch(f"{_DIGEST}.async_session", job_session_factory), patch(
        f"{_DIGEST}.send_digest_email", new_callable=AsyncMock, return_value=True
    ):
        await build_first_digest_for_user(user.id)
        await build_first_digest_for_user(user.id)  # second call must no-op

    digests = (await db.execute(select(Digest).where(Digest.user_id == user.id))).scalars().all()
    assert len(digests) == 1


async def test_first_digest_skips_user_with_no_holdings(db, job_session_factory):
    user = User(email="noholdings@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.commit()

    with patch(f"{_DIGEST}.async_session", job_session_factory), patch(
        f"{_DIGEST}.send_digest_email", new_callable=AsyncMock, return_value=True
    ):
        await build_first_digest_for_user(user.id)

    digests = (await db.execute(select(Digest).where(Digest.user_id == user.id))).scalars().all()
    assert digests == []


async def test_first_digest_does_not_inflate_quiet_streak(db, job_session_factory):
    # On-demand builds must not touch the weekly quiet-streak counter.
    user = await _seed_user_with_position(db)

    with patch(f"{_DIGEST}.async_session", job_session_factory), patch(
        f"{_DIGEST}.send_digest_email", new_callable=AsyncMock, return_value=True
    ):
        await build_first_digest_for_user(user.id)

    await db.refresh(user)
    prefs = user.preferences or {}
    assert prefs.get("consecutive_quiet_weeks", 0) == 0


async def test_generate_endpoint_returns_digest(client, auth_headers, db, test_user):
    holding = Holding(user_id=test_user.id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100, current_value=1500)
    db.add(holding)
    await db.flush()
    db.add(Thesis(
        user_id=test_user.id, holding_id=holding.id, status="active", thesis_kind="company",
        why_own_it="Quality compounder.", confidence="high", review_cadence_days=7, source="user",
    ))
    await db.commit()

    resp = await client.post("/api/digests/generate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"  # in-app preview, not emailed
    assert data["content"]["html"]


async def test_generate_endpoint_requires_a_holding(client, auth_headers):
    resp = await client.post("/api/digests/generate", headers=auth_headers)
    assert resp.status_code == 400
