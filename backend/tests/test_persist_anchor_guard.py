"""Write-time story-anchor guard.

Concurrent passes (check-now + edgar_watch + monitoring_run) each load their
dedup keys before the others commit, so read-at-start filtering alone lets the
same story persist twice. The guard re-checks anchors inside the write path.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.monitoring_pipeline import persist_classified_candidates


async def _setup(db, test_user):
    holding = Holding(
        user_id=test_user.id,
        ticker="NOW",
        name="ServiceNow",
        quantity=1,
        average_cost_basis=100,
    )
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=test_user.id,
        holding_id=holding.id,
        status="active",
        thesis_kind="company",
        why_own_it="Workflow lock-in.",
        confidence="medium",
        review_cadence_days=7,
        source="user",
    )
    db.add(thesis)
    await db.flush()
    return holding, thesis


def _candidate(article_id: str) -> dict:
    return {
        "event_type": "gemini_news",
        "description": "NOW: Headline about renewals — summary text",
        "evidence": {
            "article_id": article_id,
            "headline": "Headline about renewals",
            "url": "https://real.example/article",
            "signal_direction": "supports",
        },
    }


@pytest.mark.asyncio
async def test_same_anchor_not_persisted_twice_across_calls(db, test_user):
    holding, thesis = await _setup(db, test_user)
    now = datetime.now(timezone.utc)

    first = await persist_classified_candidates(
        db, thesis=thesis, holding=holding,
        classified=[(_candidate("stable123"), "info", "analysis")],
        claims_by_id={}, signals_by_id={}, now=now,
    )
    await db.commit()
    second = await persist_classified_candidates(
        db, thesis=thesis, holding=holding,
        classified=[(_candidate("stable123"), "info", "analysis")],
        claims_by_id={}, signals_by_id={}, now=now,
    )
    await db.commit()

    assert len(first) == 1
    assert second == []
    total = (await db.execute(MonitoringEvent.__table__.select())).all()
    assert len(total) == 1


@pytest.mark.asyncio
async def test_same_anchor_within_one_batch_persists_once(db, test_user):
    holding, thesis = await _setup(db, test_user)
    now = datetime.now(timezone.utc)

    created = await persist_classified_candidates(
        db, thesis=thesis, holding=holding,
        classified=[
            (_candidate("stable123"), "info", "analysis"),
            (_candidate("stable123"), "info", "analysis"),
        ],
        claims_by_id={}, signals_by_id={}, now=now,
    )
    await db.commit()

    assert len(created) == 1


@pytest.mark.asyncio
async def test_different_anchor_still_persists(db, test_user):
    holding, thesis = await _setup(db, test_user)
    now = datetime.now(timezone.utc)

    await persist_classified_candidates(
        db, thesis=thesis, holding=holding,
        classified=[(_candidate("stable123"), "info", "analysis")],
        claims_by_id={}, signals_by_id={}, now=now,
    )
    await db.commit()
    created = await persist_classified_candidates(
        db, thesis=thesis, holding=holding,
        classified=[(_candidate("other456"), "info", "analysis")],
        claims_by_id={}, signals_by_id={}, now=now,
    )
    await db.commit()

    assert len(created) == 1
