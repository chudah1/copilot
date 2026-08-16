"""Read side of the decision mirror — turns captured/resolved snapshots into the
surfaces that get woven into the product (starting with the weekly digest).

Capture = decision_snapshots, resolution = decision_resolution; this is the query
layer the digest / position page / quarterly review read from.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.thesis import Thesis


def _norm(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _clean(ticker: str) -> str:
    return ticker.replace("_US_EQ", "").replace("_EQ", "")


async def get_mirror_for_digest(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    period_start: datetime,
    period_end: datetime,
    now: datetime,
    limit: int = 5,
) -> dict:
    """The week's reads (snapshots resolved during the digest period) plus the
    user's open conviction bets (unresolved, soonest next-test first)."""
    read_rows = (
        await db.execute(
            select(DecisionSnapshot, Holding.ticker)
            .join(Holding, Holding.id == DecisionSnapshot.holding_id)
            .where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.resolved_at.is_not(None),
                DecisionSnapshot.resolved_at >= period_start,
                DecisionSnapshot.resolved_at <= period_end,
            )
            .order_by(DecisionSnapshot.resolved_at.desc())
            .limit(limit)
        )
    ).all()
    reads = [
        {"ticker": _clean(ticker), "bucket": snap.bucket, "read": (snap.resolution_json or {}).get("read")}
        for snap, ticker in read_rows
        if (snap.resolution_json or {}).get("read")
    ]

    open_rows = (
        await db.execute(
            select(DecisionSnapshot, Holding.ticker)
            .join(Holding, Holding.id == DecisionSnapshot.holding_id)
            .where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.resolved_at.is_(None),
            )
        )
    ).all()
    open_bets = []
    for snap, ticker in open_rows:
        nt = _norm(snap.next_test_at)
        open_bets.append(
            {
                "ticker": _clean(ticker),
                "bucket": snap.bucket,
                "bet_text": snap.bet_text,
                "next_test_at": nt.isoformat() if nt else None,
                "days_until": (nt - now).days if nt else None,
            }
        )
    # Soonest test first; bets with no scheduled test sink to the bottom.
    open_bets.sort(key=lambda b: (b["days_until"] is None, b["days_until"] if b["days_until"] is not None else 0))
    open_bets = open_bets[:limit]

    return {"reads": reads, "open_bets": open_bets}


async def get_decisions_for_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    *,
    now: datetime,
    limit: int = 20,
) -> list[dict]:
    """Every conviction call on one position, newest first — with its read if
    resolved, or its next-test countdown if still open. The per-name context for
    the position page."""
    rows = (
        await db.execute(
            select(DecisionSnapshot, Thesis.why_own_it)
            .join(Thesis, Thesis.id == DecisionSnapshot.thesis_id)
            .where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.holding_id == holding_id,
            )
            .order_by(DecisionSnapshot.decided_at.desc())
            .limit(limit * 2)
        )
    ).all()

    out = []
    recent_check_ins: dict[tuple, datetime] = {}
    for snap, written_case in rows:
        resolved = snap.resolved_at is not None
        nt = _norm(snap.next_test_at)
        decided_at = _norm(snap.decided_at)
        if snap.decision_source == "thesis_check_in" and decided_at:
            fingerprint = (
                snap.bucket,
                snap.verdict,
                snap.bet_text,
                (snap.condition_snapshot or {}).get("verdict_note"),
            )
            newer_duplicate_at = recent_check_ins.get(fingerprint)
            if newer_duplicate_at and newer_duplicate_at.date() == decided_at.date():
                continue
            recent_check_ins[fingerprint] = decided_at
        follow_up_at = nt or (decided_at + timedelta(days=90) if decided_at else None)
        bet_text = snap.bet_text
        if snap.decision_source == "thesis_check_in" and (bet_text or "").startswith("Thesis check-in:"):
            bet_text = written_case
        out.append(
            {
                "id": str(snap.id),
                "bucket": snap.bucket,
                "verdict": snap.verdict,
                "decision_source": snap.decision_source,
                "decided_at": decided_at.isoformat() if decided_at else None,
                "bet_text": bet_text,
                "resolved": resolved,
                "read": (snap.resolution_json or {}).get("read") if resolved else None,
                "next_test_days": (nt - now).days if (not resolved and nt) else None,
                "follow_up_at": follow_up_at.isoformat() if (not resolved and follow_up_at) else None,
            }
        )
        if len(out) >= limit:
            break
    return out


def _conditions_outcome(resolution_json: dict | None) -> str | None:
    """'held' if every measured condition still holds, 'broke' if any broke, None
    if the decision had no measurable condition (a vague thesis)."""
    states = [c.get("held") for c in ((resolution_json or {}).get("conditions") or []) if c.get("held") in (True, False)]
    if not states:
        return None
    return "broke" if any(s is False for s in states) else "held"


def _pattern_examples(
    snapshots: list[DecisionSnapshot],
    holdings_by_id: dict[uuid.UUID, Holding],
    *,
    limit: int = 3,
) -> list[dict]:
    rows = sorted(
        snapshots,
        key=lambda snap: _norm(snap.resolved_at) or _norm(snap.decided_at) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    examples: list[dict] = []
    for snap in rows[:limit]:
        holding = holdings_by_id.get(snap.holding_id)
        examples.append(
            {
                "ticker": _clean(holding.ticker) if holding else "?",
                "bucket": snap.bucket,
                "bet_text": snap.bet_text,
                "read": (snap.resolution_json or {}).get("read"),
                "decided_at": _norm(snap.decided_at).isoformat() if _norm(snap.decided_at) else None,
                "resolved_at": _norm(snap.resolved_at).isoformat() if _norm(snap.resolved_at) else None,
            }
        )
    return examples


async def get_decision_patterns(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    min_instances: int = 3,
) -> dict:
    """Aggregate behavioural tendencies across a user's *resolved* calls — the
    quarterly reckoning. A mirror, not a scorekeeper: neutral "N of M" instance
    counts, gated on min_instances so a tendency never gets called from one data
    point. The attention pattern is the rare-but-bulletproof claim-linked one.
    """
    snaps = (
        await db.execute(
            select(DecisionSnapshot).where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.resolved_at.is_not(None),
            )
        )
    ).scalars().all()
    holdings = (
        await db.execute(
            select(Holding).where(Holding.user_id == user_id)
        )
    ).scalars().all()
    holdings_by_id = {holding.id: holding for holding in holdings}

    patterns: list[dict] = []

    # Attention (claim-linked dismissals) — lead with this when it fires.
    dismissed = [s for s in snaps if s.bucket == "dismissed" and (s.resolution_json or {}).get("claim_followthrough")]
    hits = [s for s in dismissed if (s.resolution_json["claim_followthrough"] or {}).get("broke_after")]
    if len(dismissed) >= min_instances:
        if hits:
            patterns.append({
                "kind": "attention", "tone": "warning",
                "headline": f"Of {len(dismissed)} early warnings you dismissed, {len(hits)} were tied to a reason that later broke.",
                "detail": "You may be under-reacting to fundamental signals — worth a second look before you wave off the next one.",
                "instances": len(dismissed), "hits": len(hits),
                "examples": _pattern_examples(hits or dismissed, holdings_by_id),
            })
        else:
            patterns.append({
                "kind": "attention", "tone": "calm",
                "headline": f"Your {len(dismissed)} dismissed warnings have held up — none of those reasons later broke.",
                "detail": "Your read on what's noise has been sound so far.",
                "instances": len(dismissed), "hits": 0,
                "examples": _pattern_examples(dismissed, holdings_by_id),
            })

    # Outcome computed once per snapshot, reused for both the count and the gate.
    outcomes = [(s, s.bucket, _conditions_outcome(s.resolution_json)) for s in snaps]

    # Conviction (held through a warning).
    held = [(s, o) for s, b, o in outcomes if b == "held" and o is not None]
    if len(held) >= min_instances:
        ok = sum(1 for _, o in held if o == "held")
        patterns.append({
            "kind": "conviction", "tone": "neutral",
            "headline": f"When you held through a warning, the condition you were watching still held {ok} of {len(held)} times.",
            "detail": "How your hold calls have tracked against the reasons you wrote.",
            "instances": len(held), "hits": ok,
            "examples": _pattern_examples([snap for snap, _ in held], holdings_by_id),
        })

    # Exit (reasoning-not-regret: did the break hold up).
    exited = [(s, o) for s, b, o in outcomes if b == "exited" and o is not None]
    if len(exited) >= min_instances:
        broke = sum(1 for _, o in exited if o == "broke")
        patterns.append({
            "kind": "exit", "tone": "neutral",
            "headline": f"When you exited, the break you flagged held up {broke} of {len(exited)} times.",
            "detail": "Whether the reasons you exited on kept playing out.",
            "instances": len(exited), "hits": broke,
            "examples": _pattern_examples([snap for snap, _ in exited], holdings_by_id),
        })

    return {"patterns": patterns, "resolved_count": len(snaps)}
