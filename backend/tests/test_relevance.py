"""Tests for relevance instrumentation — the founder's read on signal vs noise."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.models.thesis_review import ThesisReview
from app.services.relevance import (
    compute_relevance_metrics,
    log_event_fired,
    log_event_reviewed,
)

_MON = "app.routes.monitoring"


async def _holding_thesis(db, user_id):
    holding = Holding(user_id=user_id, ticker="AAPL", name="Apple", quantity=10, average_cost_basis=100, current_value=1000)
    db.add(holding)
    await db.flush()
    thesis = Thesis(
        user_id=user_id, holding_id=holding.id, status="active", thesis_kind="company",
        why_own_it="Quality compounder.", confidence="high", review_cadence_days=7, source="user",
    )
    db.add(thesis)
    await db.flush()
    return holding, thesis


async def _event(db, holding, thesis, *, event_type="news_keyword_match", evidence_type="news", severity="warning", created_at=None):
    event = MonitoringEvent(
        holding_id=holding.id, thesis_id=thesis.id, event_type=event_type,
        evidence_type=evidence_type, severity=severity, title="t", summary="s",
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def _review(db, thesis, event, action, *, created_at=None):
    review = ThesisReview(
        thesis_id=thesis.id, monitoring_event_id=event.id, action=action,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(review)
    await db.flush()
    return review


async def test_metrics_with_no_reviews(db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    await _event(db, holding, thesis)
    await _event(db, holding, thesis)
    await db.commit()

    m = await compute_relevance_metrics(db, days=14)
    assert m.fired_total == 2
    assert m.reviewed_total == 0
    assert m.noise_rate is None
    assert m.review_rate == 0.0


async def test_noise_and_acted_rates(db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    e1 = await _event(db, holding, thesis)
    e2 = await _event(db, holding, thesis)
    e3 = await _event(db, holding, thesis)
    e4 = await _event(db, holding, thesis)  # fired but unreviewed
    await _review(db, thesis, e1, "not_relevant")
    await _review(db, thesis, e2, "not_relevant")
    await _review(db, thesis, e3, "reaffirmed")
    await db.commit()

    m = await compute_relevance_metrics(db, days=14)
    assert m.fired_total == 4
    assert m.reviewed_total == 3
    assert m.not_relevant == 2
    assert m.acted == 1
    assert m.noise_rate == round(2 / 3, 3)
    assert m.acted_rate == round(1 / 3, 3)
    assert m.review_rate == round(3 / 4, 3)
    assert e4 is not None


async def test_latest_review_wins(db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    e1 = await _event(db, holding, thesis)
    base = datetime.now(timezone.utc)
    await _review(db, thesis, e1, "not_relevant", created_at=base)
    await _review(db, thesis, e1, "reaffirmed", created_at=base + timedelta(minutes=5))
    await db.commit()

    m = await compute_relevance_metrics(db, days=14)
    assert m.reviewed_total == 1  # one event, not two
    assert m.not_relevant == 0    # the later "reaffirmed" wins
    assert m.acted == 1


async def test_window_excludes_old_events(db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    await _event(db, holding, thesis, created_at=datetime.now(timezone.utc) - timedelta(days=30))
    await _event(db, holding, thesis, created_at=datetime.now(timezone.utc) - timedelta(days=1))
    await db.commit()

    m = await compute_relevance_metrics(db, days=14)
    assert m.fired_total == 1  # the 30-day-old one is outside the window


async def test_breakdown_surfaces_noisiest_source_first(db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    # news source: 2 fired, both noise. price source: 1 fired, acted.
    n1 = await _event(db, holding, thesis, event_type="news_keyword_match", evidence_type="news")
    n2 = await _event(db, holding, thesis, event_type="news_keyword_match", evidence_type="news")
    p1 = await _event(db, holding, thesis, event_type="price_move", evidence_type="price")
    await _review(db, thesis, n1, "not_relevant")
    await _review(db, thesis, n2, "not_relevant")
    await _review(db, thesis, p1, "reaffirmed")
    await db.commit()

    m = await compute_relevance_metrics(db, days=14)
    # Noisiest evidence_type sorts first.
    assert m.by_evidence_type[0]["key"] == "news"
    assert m.by_evidence_type[0]["noise_rate"] == 1.0


def test_log_helpers_never_raise():
    # Even a malformed event must not break the pipeline.
    class Broken:
        id = "x"
        created_at = None
        event_type = None
        evidence_type = None
        severity = None
        verdict = None
        signal_id = None

    log_event_fired(Broken())  # must not raise
    log_event_reviewed(Broken(), "not_relevant")  # must not raise


async def test_endpoint_404_when_token_unset(client):
    with patch(f"{_MON}.settings.metrics_token", ""):
        resp = await client.get("/api/monitoring/relevance")
    assert resp.status_code == 404


async def test_endpoint_403_on_bad_token(client):
    with patch(f"{_MON}.settings.metrics_token", "secret"):
        resp = await client.get("/api/monitoring/relevance", headers={"X-Metrics-Token": "wrong"})
    assert resp.status_code == 403


async def test_endpoint_returns_metrics_with_valid_token(client, db, test_user):
    holding, thesis = await _holding_thesis(db, test_user.id)
    e1 = await _event(db, holding, thesis)
    await _review(db, thesis, e1, "not_relevant")
    await db.commit()

    with patch(f"{_MON}.settings.metrics_token", "secret"):
        resp = await client.get("/api/monitoring/relevance", headers={"X-Metrics-Token": "secret"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["fired_total"] >= 1
    assert data["noise_rate"] is not None
    assert "by_evidence_type" in data
