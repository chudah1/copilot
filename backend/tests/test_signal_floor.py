"""Tests for the monitorability floor.

Guarantee under test: every thesis — however vague or hard to parse — ends up
with at least one active monitorable signal, and decomposition never hard-fails.
"""
import uuid

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
from app.services.decomposition import (
    FLOOR_SIGNAL_SOURCE,
    _load_active_signals_with_claims,
    ensure_signal_floor,
    generate_decomposition_for_thesis,
)
from app.services.reasoning.types import ReasoningResult


class _FakeGateway:
    """Stand-in reasoning gateway that always returns a preset result."""

    def __init__(self, result: ReasoningResult):
        self._result = result

    async def run(self, request):  # noqa: ARG002 - request unused on purpose
        return self._result


def _failure_result(*, failure_reason: str, retryable: bool) -> ReasoningResult:
    return ReasoningResult(
        success=False,
        status="failed",
        provider="test-provider",
        model="test-model",
        prompt_version=None,
        normalized_output=None,
        raw_output=None,
        confidence=None,
        latency_ms=None,
        failure_reason=failure_reason,
        retryable=retryable,
    )


async def _setup(
    db,
    *,
    why: str = "Strong AI demand tailwind for the company.",
    ticker: str = "nvda",
    with_decomposition: bool = True,
    with_claim: bool = True,
    with_active_signal: bool = False,
    with_inactive_signal: bool = False,
):
    user = User(
        email=f"floor{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()

    holding = Holding(
        user_id=user.id,
        ticker=ticker,
        name="NVIDIA",
        quantity=10,
        average_cost_basis=100,
        current_price=150,
        current_value=1500,
    )
    db.add(holding)
    await db.flush()

    thesis = Thesis(
        user_id=user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it=why,
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()

    decomposition = None
    if with_decomposition:
        decomposition = ThesisDecomposition(
            thesis_id=thesis.id,
            version=1,
            status="draft",
            monitorability="low",
        )
        db.add(decomposition)
        await db.flush()

        if with_claim:
            claim = ThesisClaim(
                decomposition_id=decomposition.id,
                claim_text="AI demand stays strong",
                claim_type="growth",
                position=1,
            )
            db.add(claim)
            await db.flush()
            entity = ThesisEntity(
                claim_id=claim.id,
                entity_name="NVIDIA",
                entity_ticker="NVDA",
                entity_type="held_company",
                user_confirmed=True,
            )
            db.add(entity)
            await db.flush()
            if with_active_signal:
                sig = ThesisSignal(
                    entity_id=entity.id,
                    signal_type="revenue_growth",
                    signal_label="Revenue growth >=15%",
                    signal_config_json={"threshold": 15, "operator": ">="},
                    confidence=0.9,
                    confirmation_required=False,
                    user_confirmed=True,
                    active=True,
                )
                db.add(sig)
                await db.flush()
            if with_inactive_signal:
                sig = ThesisSignal(
                    entity_id=entity.id,
                    signal_type="revenue_growth",
                    signal_label="Revenue growth >=15%",
                    signal_config_json={"threshold": 15, "operator": ">="},
                    confidence=0.6,
                    confirmation_required=True,
                    user_confirmed=None,
                    active=False,
                )
                db.add(sig)
                await db.flush()

    await db.commit()
    return user, holding, thesis, decomposition


@pytest.mark.asyncio
async def test_floor_injected_when_no_active_signals(db):
    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)

    added = await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    assert added is True
    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 1
    sig, _claim_id = active[0]
    assert sig.signal_type == "price_move"
    assert sig.active is True
    assert sig.confirmation_required is False
    assert (sig.raw_extraction_json or {}).get("source") == FLOOR_SIGNAL_SOURCE

    assert thesis.interpretation is not None
    hints = thesis.interpretation["watch_hints"]
    assert any(h["kind"] == "price_move_pct" for h in hints)
    assert thesis.interpretation["monitorability"] == "low"


@pytest.mark.asyncio
async def test_floor_noop_when_active_signal_exists(db):
    _, holding, thesis, decomp = await _setup(db, with_active_signal=True)
    before = await _load_active_signals_with_claims(db, decomp.id)

    added = await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    assert added is False
    after = await _load_active_signals_with_claims(db, decomp.id)
    assert len(after) == len(before) == 1
    # the real signal is untouched; no floor price_move was added
    assert after[0][0].signal_type == "revenue_growth"


@pytest.mark.asyncio
async def test_floor_creates_claim_and_entity_when_decomposition_empty(db):
    _, holding, thesis, decomp = await _setup(db, with_claim=False)

    added = await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    assert added is True
    claims = (
        await db.execute(select(ThesisClaim).where(ThesisClaim.decomposition_id == decomp.id))
    ).scalars().all()
    assert len(claims) == 1
    assert claims[0].claim_type == "overall"

    entities = (
        await db.execute(select(ThesisEntity).where(ThesisEntity.claim_id == claims[0].id))
    ).scalars().all()
    assert len(entities) == 1
    assert entities[0].entity_type == "held_company"
    assert entities[0].entity_ticker == "NVDA"  # uppercased from lowercase holding ticker


@pytest.mark.asyncio
async def test_floor_reuses_existing_claim_and_entity(db):
    # claim + entity exist, but no active signal
    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)

    added = await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    assert added is True
    claims = (
        await db.execute(select(ThesisClaim).where(ThesisClaim.decomposition_id == decomp.id))
    ).scalars().all()
    assert len(claims) == 1  # reused, not duplicated
    entities = (
        await db.execute(select(ThesisEntity).where(ThesisEntity.claim_id == claims[0].id))
    ).scalars().all()
    assert len(entities) == 1  # reused
    active = await _load_active_signals_with_claims(db, decomp.id)
    assert active[0][1] == str(claims[0].id)  # floor signal attached under existing claim


@pytest.mark.asyncio
async def test_floor_is_idempotent(db):
    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)

    assert await ensure_signal_floor(db, thesis, holding, decomp) is True
    await db.commit()
    assert await ensure_signal_floor(db, thesis, holding, decomp) is False
    await db.commit()

    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 1  # no duplicate floor signal


@pytest.mark.asyncio
async def test_floor_claim_text_falls_back_when_reason_blank(db):
    # whitespace-only reason + no existing claim forces the fallback text
    _, holding, thesis, decomp = await _setup(db, why="   ", with_claim=False)

    await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    claim = (
        await db.execute(select(ThesisClaim).where(ThesisClaim.decomposition_id == decomp.id))
    ).scalars().first()
    assert claim.claim_text == f"Reason for owning {holding.ticker}"


@pytest.mark.asyncio
async def test_generate_decomposition_floors_on_nonretryable_failure(db, monkeypatch):
    _, holding, thesis, _ = await _setup(db, with_decomposition=False)
    monkeypatch.setattr(
        "app.services.decomposition.get_reasoning_gateway",
        lambda: _FakeGateway(_failure_result(failure_reason="confidence too low", retryable=False)),
    )

    result = await generate_decomposition_for_thesis(db, thesis, holding)

    assert result.decomposition is not None
    assert result.status == "draft"
    assert "baseline monitoring" in (result.message or "")

    d = result.decomposition
    assert d.status == "partially_confirmed"
    assert d.monitorability == "low"

    active = await _load_active_signals_with_claims(db, d.id)
    assert len(active) == 1
    assert active[0][0].signal_type == "price_move"

    # The floor decomposition is usable by the monitoring pipeline immediately.
    from app.services.signal_matching import load_active_decomposition

    loaded = await load_active_decomposition(db, thesis.id)
    assert loaded is not None
    assert len(loaded.claims) >= 1

    assert thesis.interpretation is not None
    assert thesis.interpretation["watch_hints"]


@pytest.mark.asyncio
async def test_confirm_rejecting_everything_respects_agency_no_floor(db):
    """Explicit rejection of all signals is honored — no floor is forced.

    The floor handles *inability* to produce signals (decomposition failure),
    not a deliberate choice to stop monitoring.
    """
    from app.services.decomposition import confirm_decomposition_for_thesis

    _, holding, thesis, decomp = await _setup(db, with_inactive_signal=True)
    assert await _load_active_signals_with_claims(db, decomp.id) == []

    entity = (await db.execute(select(ThesisEntity))).scalars().first()
    sig = (await db.execute(select(ThesisSignal))).scalars().first()

    result = await confirm_decomposition_for_thesis(
        db,
        thesis=thesis,
        holding=holding,
        decomposition_id=decomp.id,
        entity_confirmations=[{"id": entity.id, "user_confirmed": False}],
        signal_confirmations=[{"id": sig.id, "user_confirmed": False, "active": False}],
    )

    assert result is not None
    assert result.status == "rejected"
    # No floor injected; nothing active; monitoring intentionally cleared.
    assert await _load_active_signals_with_claims(db, decomp.id) == []
    assert thesis.interpretation is None


@pytest.mark.asyncio
async def test_confirm_keeping_a_real_signal_does_not_add_floor(db):
    from app.services.decomposition import confirm_decomposition_for_thesis

    _, holding, thesis, decomp = await _setup(db, with_inactive_signal=True)
    entity = (await db.execute(select(ThesisEntity))).scalars().first()
    sig = (await db.execute(select(ThesisSignal))).scalars().first()

    await confirm_decomposition_for_thesis(
        db,
        thesis=thesis,
        holding=holding,
        decomposition_id=decomp.id,
        entity_confirmations=[{"id": entity.id, "user_confirmed": True}],
        signal_confirmations=[{"id": sig.id, "user_confirmed": True, "active": True}],
    )

    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 1
    # the user's real signal is active; no floor price_move was injected
    assert active[0][0].signal_type == "revenue_growth"


@pytest.mark.asyncio
async def test_floor_uses_default_price_threshold(db):
    """The floor reuses the product's standard price sensitivity, not a coarser
    value — so flooring never regresses sensitivity vs the default fallback."""
    from app.services.monitoring import DEFAULT_PRICE_THRESHOLD_PCT

    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)
    await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    active = await _load_active_signals_with_claims(db, decomp.id)
    sig = active[0][0]
    assert sig.signal_config_json["threshold_pct"] == DEFAULT_PRICE_THRESHOLD_PCT


@pytest.mark.asyncio
async def test_floor_signal_survives_signal_decay(db):
    """Floor signals are exempt from auto-deactivation on repeated ignores —
    otherwise the dead-thesis hole the floor prevents would silently reopen."""
    from app.models.monitoring_event import MonitoringEvent
    from app.services.monitoring_review import review_monitoring_event

    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)
    claim = (await db.execute(select(ThesisClaim))).scalars().first()
    entity = (await db.execute(select(ThesisEntity))).scalars().first()
    floor = ThesisSignal(
        entity_id=entity.id,
        signal_type="price_move",
        signal_label="Price moves more than 5%",
        signal_config_json={"threshold_pct": 5.0},
        confidence=0.4,
        confirmation_required=False,
        user_confirmed=True,
        active=True,
        raw_extraction_json={"source": FLOOR_SIGNAL_SOURCE},
    )
    db.add(floor)
    await db.flush()
    event = MonitoringEvent(
        holding_id=holding.id,
        thesis_id=thesis.id,
        event_type="price_move",
        severity="warning",
        title="Price moved",
        summary="Price moved sharply.",
        signal_id=floor.id,
    )
    db.add(event)
    await db.commit()

    # Ignore well past the decay threshold.
    for _ in range(4):
        await review_monitoring_event(db, event=event, thesis=thesis, action="ignored", notes=None)
        await db.commit()

    await db.refresh(floor)
    assert floor.consecutive_ignores >= 3
    assert floor.active is True  # exempt — still watching


@pytest.mark.asyncio
async def test_floor_skips_rejected_entity_when_reusing(db):
    """When reusing an existing claim, never attach the floor signal under an
    entity the user explicitly rejected; create a fresh entity instead."""
    _, holding, thesis, decomp = await _setup(db, with_active_signal=False)
    rejected = (await db.execute(select(ThesisEntity))).scalars().first()
    rejected.user_confirmed = False
    await db.commit()

    await ensure_signal_floor(db, thesis, holding, decomp)
    await db.commit()

    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 1
    sig = active[0][0]
    floor_entity = (
        await db.execute(select(ThesisEntity).where(ThesisEntity.id == sig.entity_id))
    ).scalar_one()
    assert floor_entity.id != rejected.id
    assert floor_entity.user_confirmed is True


@pytest.mark.asyncio
async def test_floor_failure_writes_conviction_log_entry(db, monkeypatch):
    from app.models.conviction_log_entry import ConvictionLogEntry

    _, holding, thesis, _ = await _setup(db, with_decomposition=False)
    monkeypatch.setattr(
        "app.services.decomposition.get_reasoning_gateway",
        lambda: _FakeGateway(_failure_result(failure_reason="confidence too low", retryable=False)),
    )

    await generate_decomposition_for_thesis(db, thesis, holding)

    entries = (
        await db.execute(
            select(ConvictionLogEntry).where(
                ConvictionLogEntry.thesis_id == thesis.id,
                ConvictionLogEntry.entry_type == "floor_applied",
            )
        )
    ).scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_generate_decomposition_floors_on_retryable_failure(db, monkeypatch):
    _, holding, thesis, _ = await _setup(db, with_decomposition=False)
    monkeypatch.setattr(
        "app.services.decomposition.get_reasoning_gateway",
        lambda: _FakeGateway(_failure_result(failure_reason="network blip", retryable=True)),
    )

    result = await generate_decomposition_for_thesis(db, thesis, holding)

    assert result.decomposition is not None
    assert result.status == "draft"
    active = await _load_active_signals_with_claims(db, result.decomposition.id)
    assert len(active) == 1
    assert active[0][0].signal_type == "price_move"
