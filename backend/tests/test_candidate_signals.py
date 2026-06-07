"""Tests for structured candidate signals produced by the stress-test, and for
persisting confirmed candidates as active monitorable signals."""
import uuid as _uuid

import pytest
from sqlalchemy import select

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.user import User
from app.services.ai_thesis import _fallback_stress_test, _parse_candidate_signals
from app.services.auth import hash_password
from app.services.decomposition import (
    _load_active_signals_with_claims,
    apply_candidate_signals_to_thesis,
)
from app.services.stress_test import CANDIDATE_SIGNAL_TYPES, CandidateSignal


def test_parse_valid_candidate_signals():
    raw = [
        {"signal_type": "revenue_growth", "operator": ">=", "threshold_pct": 8, "label": "Rev growth above 8%", "rationale": "r"},
        {"signal_type": "price_move", "operator": None, "threshold_pct": 15, "label": "Big move", "rationale": "r"},
    ]
    out = _parse_candidate_signals(raw)
    assert len(out) == 2
    assert out[0].signal_type == "revenue_growth"
    assert out[0].operator == ">="
    assert out[0].threshold_pct == 8.0
    assert out[1].signal_type == "price_move"
    assert out[1].operator is None


def test_parse_rejects_unmonitorable_signal_type():
    # gross_margin isn't watched by the pipeline today — must be dropped.
    raw = [{"signal_type": "gross_margin", "operator": ">=", "threshold_pct": 60, "label": "Margin", "rationale": "r"}]
    assert _parse_candidate_signals(raw) == []


def test_parse_rejects_missing_label_or_threshold():
    assert _parse_candidate_signals([{"signal_type": "revenue_growth", "threshold_pct": 8}]) == []  # no label
    assert _parse_candidate_signals([{"signal_type": "revenue_growth", "label": "x"}]) == []  # no threshold


def test_parse_defaults_operator_for_growth_metric():
    out = _parse_candidate_signals([{"signal_type": "earnings_growth", "threshold_pct": 5, "label": "EPS growth"}])
    assert out[0].operator == ">="


def test_parse_caps_at_three():
    raw = [{"signal_type": "price_move", "threshold_pct": i, "label": f"m{i}"} for i in range(5)]
    assert len(_parse_candidate_signals(raw)) == 3


def test_parse_handles_non_dict_and_garbage():
    assert _parse_candidate_signals(None) == []
    assert _parse_candidate_signals(["not a dict", 42]) == []
    assert _parse_candidate_signals([{"signal_type": "price_move", "threshold_pct": "abc", "label": "x"}]) == []


def test_parse_rejects_non_finite_or_out_of_range_threshold():
    assert _parse_candidate_signals([{"signal_type": "price_move", "threshold_pct": float("inf"), "label": "x"}]) == []
    assert _parse_candidate_signals([{"signal_type": "price_move", "threshold_pct": float("nan"), "label": "x"}]) == []
    assert _parse_candidate_signals([{"signal_type": "price_move", "threshold_pct": -5, "label": "x"}]) == []
    assert _parse_candidate_signals([{"signal_type": "price_move", "threshold_pct": 99999, "label": "x"}]) == []


def test_fallback_includes_monitorable_candidate_signals():
    out = _fallback_stress_test("NVDA", "some thesis")
    assert out.candidate_signals
    assert all(c.signal_type in CANDIDATE_SIGNAL_TYPES for c in out.candidate_signals)
    # the fallback should offer at least one qualitative watch too
    assert any(c.signal_type == "news_watch" for c in out.candidate_signals)


# --- qualitative news_watch candidate signals ------------------------------

def test_parse_news_watch_signal():
    raw = [{"signal_type": "news_watch", "watch_for": "AMD lands a major design win",
            "direction": "threatens", "label": "Competitor win", "rationale": "r"}]
    out = _parse_candidate_signals(raw)
    assert len(out) == 1
    s = out[0]
    assert s.signal_type == "news_watch"
    assert s.watch_for == "AMD lands a major design win"
    assert s.direction == "threatens"


def test_parse_news_watch_requires_watch_for():
    raw = [{"signal_type": "news_watch", "direction": "threatens", "label": "x"}]
    assert _parse_candidate_signals(raw) == []


def test_parse_news_watch_defaults_direction():
    raw = [{"signal_type": "news_watch", "watch_for": "Something happens", "label": "x", "direction": "bogus"}]
    out = _parse_candidate_signals(raw)
    assert out[0].direction == "threatens"


# --- persistence: confirmed candidates -> active monitorable signals ---------

async def _make_thesis(db):
    user = User(email=f"cand{_uuid.uuid4().hex[:8]}@example.com", password_hash=hash_password("testpass123"))
    db.add(user)
    await db.flush()
    holding = Holding(
        user_id=user.id, ticker="nvda", name="NVIDIA",
        quantity=10, average_cost_basis=100, current_price=150, current_value=1500,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=user.id, holding_id=holding.id, status="active", thesis_kind="company",
        why_own_it="AI demand tailwind.", confidence="medium", review_cadence_days=7, source="user",
    )
    db.add(thesis)
    await db.flush()
    await db.commit()
    return user, holding, thesis


@pytest.mark.asyncio
async def test_apply_candidate_signals_persists_active_and_syncs_units(db):
    _, holding, thesis = await _make_thesis(db)
    candidates = [
        CandidateSignal("revenue_growth", "Revenue growth stays above 8%", 8.0, "r", ">="),
        CandidateSignal("price_move", "Sharp move 15%", 15.0, "r", None),
    ]
    applied = await apply_candidate_signals_to_thesis(db, thesis, holding, candidates)
    await db.commit()

    assert applied == 2
    decomp = (
        await db.execute(select(ThesisDecomposition).where(ThesisDecomposition.thesis_id == thesis.id))
    ).scalars().first()
    assert decomp.status == "partially_confirmed"
    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 2

    by_type = {s.signal_type: s for s, _ in active}
    # growth threshold persisted as a FRACTION (market feed uses 0.08, not 8)
    assert by_type["revenue_growth"].signal_config_json == {"threshold": 0.08, "operator": ">="}
    # price move stays in percent
    assert by_type["price_move"].signal_config_json == {"threshold_pct": 15.0}
    # interpretation rebuilt so monitoring picks these up
    assert thesis.interpretation and thesis.interpretation["watch_hints"]


@pytest.mark.asyncio
async def test_apply_news_watch_persists_with_qualitative_config(db):
    _, holding, thesis = await _make_thesis(db)
    candidates = [
        CandidateSignal(signal_type="news_watch", label="Competitor design win",
                        rationale="r", watch_for="AMD lands a major design win", direction="threatens"),
    ]
    applied = await apply_candidate_signals_to_thesis(db, thesis, holding, candidates)
    await db.commit()

    assert applied == 1
    decomp = (
        await db.execute(select(ThesisDecomposition).where(ThesisDecomposition.thesis_id == thesis.id))
    ).scalars().first()
    active = await _load_active_signals_with_claims(db, decomp.id)
    assert len(active) == 1
    sig = active[0][0]
    assert sig.signal_type == "news_watch"
    assert sig.signal_config_json == {"watch_for": "AMD lands a major design win", "direction": "threatens"}


@pytest.mark.asyncio
async def test_confirm_signals_endpoint_accepts_news_watch(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    thesis = await client.post(
        "/api/theses",
        json={"holding_id": holding.json()["id"], "status": "active", "thesis_kind": "company",
              "why_own_it": "AI demand tailwind.", "confidence": "medium",
              "what_would_change_my_mind": "Revenue decline for two consecutive quarters.",
              "review_cadence_days": 7, "source": "user"},
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/onboarding/confirm-signals",
        json={"thesis_id": thesis.json()["id"], "signals": [
            {"signal_type": "news_watch", "label": "Competitor win",
             "watch_for": "AMD lands a major design win", "direction": "threatens", "rationale": "r"},
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1


@pytest.mark.asyncio
async def test_apply_candidate_signals_ignores_unmonitorable_types(db):
    _, holding, thesis = await _make_thesis(db)
    candidates = [CandidateSignal("gross_margin", "Margin above 60%", 60.0, "r", ">=")]
    applied = await apply_candidate_signals_to_thesis(db, thesis, holding, candidates)
    await db.commit()
    assert applied == 0


@pytest.mark.asyncio
async def test_confirm_signals_endpoint_applies_to_thesis(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    thesis = await client.post(
        "/api/theses",
        json={
            "holding_id": holding.json()["id"],
            "status": "active", "thesis_kind": "company",
            "why_own_it": "AI demand tailwind.", "confidence": "medium",
            "what_would_change_my_mind": "Revenue decline for two consecutive quarters.",
            "review_cadence_days": 7, "source": "user",
        },
        headers=auth_headers,
    )
    assert thesis.status_code == 201

    resp = await client.post(
        "/api/onboarding/confirm-signals",
        json={
            "thesis_id": thesis.json()["id"],
            "signals": [
                {"signal_type": "revenue_growth", "label": "Rev growth above 8%", "threshold_pct": 8, "operator": ">=", "rationale": "r"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1


@pytest.mark.asyncio
async def test_confirm_signals_rejects_unsupported_type_at_boundary(client, auth_headers):
    holding = await client.post(
        "/api/portfolio/holdings",
        json={"ticker": "NVDA", "name": "NVIDIA", "quantity": 2, "average_cost_basis": 900},
        headers=auth_headers,
    )
    thesis = await client.post(
        "/api/theses",
        json={
            "holding_id": holding.json()["id"], "status": "active", "thesis_kind": "company",
            "why_own_it": "AI demand tailwind.", "confidence": "medium",
            "what_would_change_my_mind": "Revenue decline for two consecutive quarters.",
            "review_cadence_days": 7, "source": "user",
        },
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/onboarding/confirm-signals",
        json={
            "thesis_id": thesis.json()["id"],
            "signals": [{"signal_type": "gross_margin", "label": "x", "threshold_pct": 60}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422  # unsupported type rejected, no silent drop


@pytest.mark.asyncio
async def test_apply_candidate_signals_is_idempotent(db):
    _, holding, thesis = await _make_thesis(db)
    candidates = [CandidateSignal("revenue_growth", "Revenue growth above 8%", 8.0, "r", ">=")]

    first = await apply_candidate_signals_to_thesis(db, thesis, holding, candidates)
    await db.commit()
    second = await apply_candidate_signals_to_thesis(db, thesis, holding, candidates)
    await db.commit()

    assert first == 1
    assert second == 0  # same watch not duplicated
    decomp = (
        await db.execute(select(ThesisDecomposition).where(ThesisDecomposition.thesis_id == thesis.id))
    ).scalars().all()
    assert len(decomp) == 1  # no second decomposition created
    active = await _load_active_signals_with_claims(db, decomp[0].id)
    assert len(active) == 1


@pytest.mark.asyncio
async def test_confirm_signals_404_for_unknown_thesis(client, auth_headers):
    resp = await client.post(
        "/api/onboarding/confirm-signals",
        json={"thesis_id": str(_uuid.uuid4()), "signals": []},
        headers=auth_headers,
    )
    assert resp.status_code == 404
