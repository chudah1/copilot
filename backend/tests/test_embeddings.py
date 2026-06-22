import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.services.auth import hash_password
from app.services.decomposition import confirm_decomposition_for_thesis


async def _setup_confirmable_decomposition(db):
    user = User(
        email=f"embed{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker="AAPL",
        name="Apple Inc.",
        quantity=5,
        average_cost_basis=100,
        current_price=150,
        current_value=750,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Services keeps compounding.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=1,
        status="draft",
        monitorability="medium",
    )
    db.add(decomposition)
    await db.flush()

    claim = ThesisClaim(
        decomposition_id=decomposition.id,
        claim_text="Services growth remains durable",
        claim_type="growth",
        position=1,
    )
    db.add(claim)
    await db.flush()

    entity = ThesisEntity(
        claim_id=claim.id,
        entity_name="Apple Inc.",
        entity_ticker="AAPL",
        entity_type="held_company",
        user_confirmed=None,
    )
    db.add(entity)
    await db.flush()

    signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="revenue_growth",
        signal_label="Services revenue growth stays strong",
        signal_config_json={"metric": "revenue_growth_yoy"},
        confidence=0.9,
        confirmation_required=False,
        user_confirmed=None,
        active=False,
    )
    db.add(signal)
    await db.commit()

    return holding, thesis, decomposition, claim, entity, signal


@pytest.mark.asyncio
async def test_confirmed_decomposition_persists_claim_embedding(db):
    holding, thesis, decomposition, claim, entity, signal = await _setup_confirmable_decomposition(db)
    claim_id = claim.id
    expected_text = "Services growth remains durable\nSignals: Services revenue growth stays strong"

    with patch(
        "app.services.decomposition.embed_text_map",
        new=AsyncMock(return_value={expected_text: [0.1, 0.2, 0.3]}),
    ) as mock_embed:
        result = await confirm_decomposition_for_thesis(
            db,
            thesis=thesis,
            holding=holding,
            decomposition_id=decomposition.id,
            entity_confirmations=[{"id": entity.id, "user_confirmed": True}],
            signal_confirmations=[{"id": signal.id, "user_confirmed": True, "active": True}],
        )

    assert result is not None
    assert result.status == "confirmed"
    mock_embed.assert_awaited_once()

    refreshed_claim = (
        await db.execute(select(ThesisClaim).where(ThesisClaim.id == claim_id))
    ).scalar_one()
    assert refreshed_claim.embedding_text == expected_text
    assert refreshed_claim.embedding == [0.1, 0.2, 0.3]
    assert refreshed_claim.embedded_at is not None


@pytest.mark.asyncio
async def test_rejected_decomposition_clears_existing_claim_embedding(db):
    holding, thesis, decomposition, claim, entity, signal = await _setup_confirmable_decomposition(db)
    claim_id = claim.id
    claim.embedding_text = "stale"
    claim.embedding = [0.9, 0.8]
    await db.commit()

    with patch(
        "app.services.decomposition.embed_text_map",
        new=AsyncMock(return_value={"unused": [0.1]}),
    ) as mock_embed:
        result = await confirm_decomposition_for_thesis(
            db,
            thesis=thesis,
            holding=holding,
            decomposition_id=decomposition.id,
            entity_confirmations=[{"id": entity.id, "user_confirmed": False}],
            signal_confirmations=[{"id": signal.id, "user_confirmed": False, "active": False}],
        )

    assert result is not None
    assert result.status == "rejected"
    mock_embed.assert_not_awaited()

    refreshed_claim = (
        await db.execute(select(ThesisClaim).where(ThesisClaim.id == claim_id))
    ).scalar_one()
    assert refreshed_claim.embedding_text is None
    assert refreshed_claim.embedding is None
    assert refreshed_claim.embedded_at is None
