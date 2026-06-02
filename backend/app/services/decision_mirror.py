"""Read side of the decision mirror — turns captured/resolved snapshots into the
surfaces that get woven into the product (starting with the weekly digest).

Capture = decision_snapshots, resolution = decision_resolution; this is the query
layer the digest / position page / quarterly review read from.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding


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
            select(DecisionSnapshot)
            .where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.holding_id == holding_id,
            )
            .order_by(DecisionSnapshot.decided_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    out = []
    for snap in rows:
        resolved = snap.resolved_at is not None
        nt = _norm(snap.next_test_at)
        out.append(
            {
                "id": str(snap.id),
                "bucket": snap.bucket,
                "verdict": snap.verdict,
                "decision_source": snap.decision_source,
                "decided_at": _norm(snap.decided_at).isoformat() if snap.decided_at else None,
                "bet_text": snap.bet_text,
                "resolved": resolved,
                "read": (snap.resolution_json or {}).get("read") if resolved else None,
                "next_test_days": (nt - now).days if (not resolved and nt) else None,
            }
        )
    return out
