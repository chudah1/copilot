"""Tests for the decision-mirror read layer + its surfacing in the digest."""
from datetime import datetime, timedelta, timezone

from app.jobs.digest_builder import _render_digest_html
from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.decision_mirror import (
    get_decision_patterns,
    get_decisions_for_holding,
    get_mirror_for_digest,
)

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
        decision_source=kw.get("decision_source", "event_review"), decided_at=kw.get("decided_at", _NOW - timedelta(days=40)),
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


# ── per-holding decisions (position page) ────────────────────────────────────

async def test_get_decisions_for_holding_newest_first_with_read_and_countdown(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    db.add(_snap(test_user.id, h, t, decided_at=_NOW - timedelta(days=50),
                 resolved_at=_NOW - timedelta(days=2),
                 resolution_json={"read": "You held; conditions still hold."}))
    db.add(_snap(test_user.id, h, t, decided_at=_NOW - timedelta(days=1),
                 resolved_at=None, next_test_at=_NOW + timedelta(days=12)))
    await db.commit()

    rows = await get_decisions_for_holding(db, test_user.id, h.id, now=_NOW)
    assert len(rows) == 2
    assert rows[0]["resolved"] is False and rows[0]["next_test_days"] == 12  # newest first
    assert rows[0]["follow_up_at"] == (_NOW + timedelta(days=12)).isoformat()
    assert rows[1]["resolved"] is True and "still hold" in rows[1]["read"]


async def test_open_decision_without_earnings_uses_90_day_follow_up(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    decided_at = _NOW - timedelta(days=10)
    db.add(_snap(test_user.id, h, t, decided_at=decided_at, resolved_at=None, next_test_at=None))
    await db.commit()

    rows = await get_decisions_for_holding(db, test_user.id, h.id, now=_NOW)

    assert rows[0]["follow_up_at"] == (decided_at + timedelta(days=90)).isoformat()


async def test_decisions_collapse_accidental_duplicate_check_ins(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    for seconds in (0, 60 * 60):
        db.add(_snap(
            test_user.id,
            h,
            t,
            decision_source="thesis_check_in",
            decided_at=_NOW + timedelta(seconds=seconds),
            bet_text="Cloud stays durable.",
        ))
    await db.commit()

    rows = await get_decisions_for_holding(db, test_user.id, h.id, now=_NOW)

    assert len(rows) == 1


async def test_decisions_keep_different_check_ins_from_the_same_day(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    db.add(_snap(
        test_user.id,
        h,
        t,
        decision_source="thesis_check_in",
        decided_at=_NOW,
        bet_text="Cloud stays durable.",
    ))
    db.add(_snap(
        test_user.id,
        h,
        t,
        decision_source="thesis_check_in",
        decided_at=_NOW + timedelta(hours=1),
        bet_text="AI revenue is becoming meaningful.",
    ))
    await db.commit()

    rows = await get_decisions_for_holding(db, test_user.id, h.id, now=_NOW)

    assert len(rows) == 2


async def test_legacy_check_in_summary_falls_back_to_written_case(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    db.add(_snap(
        test_user.id,
        h,
        t,
        decision_source="thesis_check_in",
        bet_text="Thesis check-in: 1 holds.",
    ))
    await db.commit()

    rows = await get_decisions_for_holding(db, test_user.id, h.id, now=_NOW)

    assert rows[0]["bet_text"] == "Cloud."


async def test_decisions_endpoint_returns_calls(client, auth_headers, db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    db.add(_snap(test_user.id, h, t, resolved_at=None, next_test_at=_NOW + timedelta(days=5)))
    await db.commit()

    resp = await client.get(f"/api/monitoring/holdings/{h.id}/decisions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["bucket"] == "held"


async def test_decisions_endpoint_404_for_unknown_holding(client, auth_headers):
    import uuid
    resp = await client.get(f"/api/monitoring/holdings/{uuid.uuid4()}/decisions", headers=auth_headers)
    assert resp.status_code == 404


# ── quarterly pattern layer ──────────────────────────────────────────────────

def _resolved(user_id, h, t, *, bucket, resolution_json):
    return _snap(user_id, h, t, bucket=bucket, resolved_at=_NOW - timedelta(days=3),
                 resolution_json=resolution_json)


async def test_no_patterns_below_min_instances(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    # only 2 dismissals — below the gate of 3
    for _ in range(2):
        db.add(_resolved(test_user.id, h, t, bucket="dismissed",
                         resolution_json={"claim_followthrough": {"broke_after": True}}))
    await db.commit()
    result = await get_decision_patterns(db, test_user.id)
    assert result["patterns"] == []
    assert result["resolved_count"] == 2


async def test_attention_warning_when_dismissals_broke(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    for broke in (True, True, False):  # 3 claim-linked dismissals, 2 broke
        db.add(_resolved(test_user.id, h, t, bucket="dismissed",
                         resolution_json={"claim_followthrough": {"broke_after": broke}}))
    await db.commit()
    pats = (await get_decision_patterns(db, test_user.id))["patterns"]
    attn = next(p for p in pats if p["kind"] == "attention")
    assert attn["tone"] == "warning"
    assert attn["instances"] == 3 and attn["hits"] == 2
    assert "under-reacting" in attn["detail"]


async def test_attention_calm_when_dismissals_held_up(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    for _ in range(3):
        db.add(_resolved(test_user.id, h, t, bucket="dismissed",
                         resolution_json={"claim_followthrough": {"broke_after": False}}))
    await db.commit()
    pats = (await get_decision_patterns(db, test_user.id))["patterns"]
    attn = next(p for p in pats if p["kind"] == "attention")
    assert attn["tone"] == "calm" and attn["hits"] == 0


async def test_conviction_and_exit_patterns(db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    # held: 2 held, 1 broke
    for held in (True, True, False):
        db.add(_resolved(test_user.id, h, t, bucket="held",
                         resolution_json={"conditions": [{"metric": "m", "held": held}]}))
    # exited: 2 breaks held up, 1 reversed
    for held in (False, False, True):
        db.add(_resolved(test_user.id, h, t, bucket="exited",
                         resolution_json={"conditions": [{"metric": "m", "held": held}]}))
    await db.commit()
    pats = {p["kind"]: p for p in (await get_decision_patterns(db, test_user.id))["patterns"]}
    assert pats["conviction"]["hits"] == 2 and pats["conviction"]["instances"] == 3
    assert pats["exit"]["hits"] == 2 and pats["exit"]["instances"] == 3


async def test_patterns_endpoint(client, auth_headers, db, test_user):
    h, t = await _holding_thesis(db, test_user.id)
    for broke in (True, True, True):
        db.add(_resolved(test_user.id, h, t, bucket="dismissed",
                         resolution_json={"claim_followthrough": {"broke_after": broke}}))
    await db.commit()
    resp = await client.get("/api/quarterly-review/patterns", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_count"] == 3
    assert any(p["kind"] == "attention" for p in data["patterns"])
