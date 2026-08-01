import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thesis_health import compute_health_score

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _event(severity: str, verdict: str, age_days: float = 0, claim_id=None, event_id=None):
    e = MagicMock()
    e.id = event_id or uuid.uuid4()
    e.severity = severity
    e.verdict = verdict
    e.claim_id = claim_id
    e.created_at = NOW - timedelta(days=age_days)
    return e


def _claim(claim_id, confidence: float):
    c = MagicMock()
    c.id = claim_id
    c.confidence = confidence
    return c


# --- Behavior 1: no events, no decomposition → default 75 Healthy ---

def test_no_events_no_decomposition_returns_default():
    score, label = compute_health_score(
        decomposition_confidence=None,
        events=[],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 75
    assert label == "Healthy"


# --- Behavior 2: no events, high decomposition confidence → high score ---

def test_no_events_high_decomposition_confidence():
    score, label = compute_health_score(
        decomposition_confidence=0.9,
        events=[],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 90
    assert label == "Healthy"


# --- Behavior 3: no events, low decomposition confidence → At Risk ---

def test_no_events_low_decomposition_confidence():
    score, label = compute_health_score(
        decomposition_confidence=0.5,
        events=[],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 50
    assert label == "At Risk"


# --- Behavior 4: thesis_breaking + threatens → heavy deduction ---

def test_thesis_breaking_threatens_deducts_heavily():
    base_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("thesis_breaking", "threatens")],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score < base_score - 25


# --- Behavior 5: warning + review → moderate deduction ---

def test_warning_review_deducts_moderately():
    score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("warning", "review")],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert 60 <= score <= 73


# --- Behavior 6: supports verdict → gains points ---

def test_supports_verdict_adds_points():
    score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("info", "supports")],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 80


def test_neutral_info_event_does_not_reduce_health():
    """Neutral evidence is a receipt, not evidence against the written case.

    This reproduces the SOFI sequence where a neutral price move took a thesis
    from 76/Healthy to 74/At Risk and caused a misleading email.
    """
    score, label = compute_health_score(
        decomposition_confidence=0.76,
        events=[_event("info", "neutral")],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 76
    assert label == "Healthy"


# --- Behavior 7: old event weighs less than fresh event ---

def test_old_event_weighs_less_than_fresh():
    fresh_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("thesis_breaking", "threatens", age_days=0)],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    old_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("thesis_breaking", "threatens", age_days=60)],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert old_score > fresh_score


# --- Behavior 8: reviewed thesis_breaking decays; unreviewed floors at 50% ---

def test_reviewed_thesis_breaking_decays_more_than_unreviewed():
    event_id = uuid.uuid4()
    reviewed_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("thesis_breaking", "threatens", age_days=90, event_id=event_id)],
        claims=[],
        reviewed_event_ids={event_id},
        now=NOW,
    )
    unreviewed_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("thesis_breaking", "threatens", age_days=90, event_id=event_id)],
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert reviewed_score > unreviewed_score


# --- Behavior 9: high-confidence claim hit deducts more than low-confidence ---

def test_high_confidence_claim_deducts_more():
    high_claim_id = uuid.uuid4()
    low_claim_id = uuid.uuid4()

    high_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("warning", "threatens", claim_id=high_claim_id)],
        claims=[_claim(high_claim_id, 0.9)],
        reviewed_event_ids=set(),
        now=NOW,
    )
    low_score, _ = compute_health_score(
        decomposition_confidence=None,
        events=[_event("warning", "threatens", claim_id=low_claim_id)],
        claims=[_claim(low_claim_id, 0.2)],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert low_score > high_score


# --- Behavior 10: score clamps between 0 and 100 ---

def test_score_clamps_to_zero():
    many_bad_events = [_event("thesis_breaking", "threatens") for _ in range(10)]
    score, label = compute_health_score(
        decomposition_confidence=None,
        events=many_bad_events,
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 0
    assert label == "Broken"


def test_score_clamps_to_hundred():
    many_good_events = [_event("info", "supports") for _ in range(20)]
    score, label = compute_health_score(
        decomposition_confidence=None,
        events=many_good_events,
        claims=[],
        reviewed_event_ids=set(),
        now=NOW,
    )
    assert score == 100
    assert label == "Healthy"


# --- Behavior 11: ThesisResponse includes health_score and health_label ---

@pytest.mark.asyncio
async def test_thesis_response_includes_health_fields(client, auth_headers):
    with patch("app.services.ai_thesis.generate_draft_theses_for_user", new_callable=AsyncMock):
        holding_resp = await client.post(
            "/api/portfolio/holdings",
            json={"ticker": "MSFT", "name": "Microsoft", "quantity": 5, "average_cost_basis": 300.0},
            headers=auth_headers,
        )
    holding_id = holding_resp.json()["id"]

    resp = await client.post(
        "/api/theses",
        json={
            "holding_id": holding_id,
            "status": "active",
            "thesis_kind": "company",
            "why_own_it": "Cloud dominance via Azure.",
            "what_would_change_my_mind": "Revenue decline or margin compression.",
            "confidence": "high",
            "source": "user",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "health_score" in data
    assert "health_label" in data
