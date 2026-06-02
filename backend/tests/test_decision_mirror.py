"""Tests for the decision-mirror read layer + its surfacing in the digest."""
from datetime import datetime, timedelta, timezone

from app.jobs.digest_builder import _render_digest_html
from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.decision_mirror import get_mirror_for_digest

_NOW = datetime(2026, 6, 2, tzinfo=timezone.utc)


async def _holding_thesis(db, user_id, ticker="MSFT"):
    h = Holding(user_id=user_id, ticker=ticker, name=ticker, quantity=5,
                average_cost_basis=200, current_price=460, current_value=1800, currency="USD")
    db.add(h)
    await db.flush()
    t = Thesis(user_id=user_id, holding_id=h.id, status="active", thesis_kind="company",
               why_own_it="Cloud.", confidence="high", review_cadence_days=7, source="user")
    db.add(t)
    await db.flush()
    return h, t


def _snap(user_id, h, t, **kw):
    return DecisionSnapshot(
        user_id=user_id, thesis_id=t.id, holding_id=h.id,
        verdict=kw.get("verdict", "reaffirmed"), bucket=kw.get("bucket", "held"),
        decision_source="event_review", decided_at=kw.get("decided_at", _NOW - timedelta(days=40)),
        price_native=460, value_gbp=1800, currency="USD", benchmark_ticker="SPY",
        next_test_at=kw.get("next_test_at"), bet_text=kw.get("bet_text", "Azure decel"),
        resolved_at=kw.get("resolved_at"), resolution_json=kw.get("resolution_json"),
        condition_snapshot={"watch_hints": []},
    )


async def test_get_mirror_returns_period_reads_and_open_bets(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    # a read resolved inside the period
    db.add(_snap(test_user.id, h, t, resolved_at=_NOW - timedelta(days=2),
                 resolution_json={"read": "You held MSFT through Azure decel. The conditions still hold."}))
    # a read resolved BEFORE the period (should be excluded)
    db.add(_snap(test_user.id, h, t, resolved_at=_NOW - timedelta(days=40),
                 resolution_json={"read": "old read"}))
    # an open bet
    db.add(_snap(test_user.id, h, t, resolved_at=None, next_test_at=_NOW + timedelta(days=9)))
    await db.commit()

    mirror = await get_mirror_for_digest(
        db, test_user.id, period_start=_NOW - timedelta(days=7), period_end=_NOW, now=_NOW
    )
    assert len(mirror["reads"]) == 1
    assert "conditions still hold" in mirror["reads"][0]["read"]
    assert len(mirror["open_bets"]) == 1
    assert mirror["open_bets"][0]["days_until"] == 9


async def test_open_bets_sorted_soonest_test_first(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    db.add(_snap(test_user.id, h, t, resolved_at=None, next_test_at=_NOW + timedelta(days=30)))
    db.add(_snap(test_user.id, h, t, resolved_at=None, next_test_at=_NOW + timedelta(days=3)))
    db.add(_snap(test_user.id, h, t, resolved_at=None, next_test_at=None))  # no test -> last
    await db.commit()

    mirror = await get_mirror_for_digest(
        db, test_user.id, period_start=_NOW - timedelta(days=7), period_end=_NOW, now=_NOW
    )
    days = [b["days_until"] for b in mirror["open_bets"]]
    assert days == [3, 30, None]


def test_render_includes_mirror_section():
    html = _render_digest_html(
        holdings_with_theses=[], events_data=[], observations={}, headline="Quiet week.",
        monitoring_receipt="Checked 1 holding.", quiet_nudge=None,
        mirror={
            "reads": [{"ticker": "MSFT", "bucket": "held", "read": "You held MSFT; conditions still hold."}],
            "open_bets": [{"ticker": "NVDA", "bucket": "held", "bet_text": "margins", "days_until": 9}],
        },
    )
    assert "How your calls are playing out" in html
    assert "You held MSFT; conditions still hold." in html
    assert "Open bets:" in html
    assert "NVDA (next test in 9d)" in html


def test_render_omits_mirror_when_empty():
    html = _render_digest_html(
        holdings_with_theses=[], events_data=[], observations={}, headline="Quiet week.",
        monitoring_receipt="Checked 1 holding.", quiet_nudge=None,
        mirror={"reads": [], "open_bets": []},
    )
    assert "How your calls are playing out" not in html
