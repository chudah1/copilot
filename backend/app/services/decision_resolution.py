"""Resolution half of the decision-mirror loop.

Reads back open decision snapshots once the bet has been tested (the next earnings
landed, or a 90-day soft-read for untested calls) and writes a neutral "what
happened" read — anchored on whether the *conditions the user bet on* played out,
not on price. This is a mirror, not a scorekeeper: the read reports facts (the
condition's state now, the price move, whether a dismissed claim later broke); it
never says the user was right or wrong.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis_claim import ThesisClaim
from app.services.market_data import fetch_company_data, fetch_live_price, fetch_price_on
from app.services.monitoring import check_metric_watch_hints

logger = logging.getLogger(__name__)

SOFT_READ_DAYS = 90
_METRIC_FIELDS = ("revenue_growth_yoy", "earnings_growth_yoy", "pe_ratio", "dividend_yield")


def _norm(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def is_ready(snapshot: DecisionSnapshot, now: datetime) -> bool:
    """A snapshot is ready once its bet has been tested: the next-earnings anchor
    has passed, or (no anchor) 90 days have elapsed for a soft read."""
    if snapshot.resolved_at is not None:
        return False
    next_test = _norm(snapshot.next_test_at)
    if next_test is not None:
        return next_test <= now
    return _norm(snapshot.decided_at) <= now - timedelta(days=SOFT_READ_DAYS)


def _market_values(company_data) -> dict[str, float]:
    values = {m: getattr(company_data, m, None) for m in _METRIC_FIELDS}
    return {k: v for k, v in values.items() if v is not None}


def _condition_reads(snapshot: DecisionSnapshot, company_data) -> list[dict]:
    """Re-read the thesis's monitored conditions against current market values via
    the canonical comparator. held = condition still satisfied (not breached)."""
    cond = snapshot.condition_snapshot or {}
    interpretation = {"watch_hints": cond.get("watch_hints") or []}
    results = check_metric_watch_hints(interpretation, _market_values(company_data))
    return [
        {
            "metric": r.metric,
            "operator": r.operator,
            "threshold": r.threshold,
            "value_now": r.actual_value,
            "held": not r.breached,
        }
        for r in results
    ]


def _price_read(snapshot: DecisionSnapshot, company_data) -> dict:
    then = float(snapshot.price_native) if snapshot.price_native is not None else None
    now = company_data.current_price if company_data else None
    pct = round((now - then) / then * 100, 1) if (then and now and then > 0) else None
    return {"then": then, "now": now, "pct": pct, "currency": snapshot.currency}


async def _benchmark_move_pct(snapshot: DecisionSnapshot) -> float | None:
    """The benchmark's % move over the same window (decision -> now). Both moves
    are unitless %, so they're comparable across currencies without FX."""
    if not snapshot.benchmark_ticker or snapshot.decided_at is None:
        return None
    then = await fetch_price_on(snapshot.benchmark_ticker, _norm(snapshot.decided_at))
    now = await fetch_live_price(snapshot.benchmark_ticker)
    if then and now and then > 0:
        return round((now - then) / then * 100, 1)
    return None


def _price_phrase(price: dict) -> str | None:
    """Muted price context — relative to the market when we have the benchmark."""
    pct = price.get("pct")
    if pct is None:
        return None
    bpct = price.get("benchmark_pct")
    if bpct is not None:
        return f"{pct:+.0f}% vs market {bpct:+.0f}%"
    return f"{pct:+.0f}% since"


async def _claim_broke_after(db: AsyncSession, snapshot: DecisionSnapshot) -> bool | None:
    """For a dismissed signal: did the *same claim* it was tied to subsequently
    break (a thesis-breaking event on that claim after the dismissal)? This is the
    only thing that earns the rare-but-bulletproof 'you under-reacted' read."""
    if snapshot.claim_id is None:
        return None
    found = (
        await db.execute(
            select(MonitoringEvent.id)
            .where(
                MonitoringEvent.claim_id == snapshot.claim_id,
                MonitoringEvent.severity == "thesis_breaking",
                MonitoringEvent.created_at > snapshot.decided_at,
                MonitoringEvent.id != snapshot.monitoring_event_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return found is not None


async def _claim_text(db: AsyncSession, claim_id) -> str | None:
    if claim_id is None:
        return None
    return (
        await db.execute(select(ThesisClaim.claim_text).where(ThesisClaim.id == claim_id))
    ).scalar_one_or_none()


def _clean(ticker: str) -> str:
    return ticker.replace("_US_EQ", "").replace("_EQ", "")


def _is_vague(snapshot: DecisionSnapshot) -> bool:
    """A decision is 'vague' (gets the weak mirror) when the thesis had nothing
    measurable to test: low monitorability, or no metric-threshold condition at
    all. These will never produce a reasoning read, so we frame the gap honestly
    and nudge toward a sharper thesis — rather than pretend a price move is one."""
    cond = snapshot.condition_snapshot or {}
    if cond.get("monitorability") == "low":
        return True
    hints = cond.get("watch_hints") or []
    return not any(h.get("kind") == "metric_threshold" for h in hints)


def _read_text(
    *, bucket: str, ticker: str, bet: str | None, conditions: list[dict],
    price: dict, claim_broke: bool | None, claim_text: str | None, vague: bool = False,
) -> str:
    t = _clean(ticker)
    bet = (bet or "this position").strip()
    phrase = _price_phrase(price)
    breached = [c for c in conditions if c["held"] is False]
    held_all = bool(conditions) and not breached
    # The weak mirror's honest framing of the price gap when there's nothing to test.
    weak_tail = (phrase or "no measurable change") + ". This reason wasn't specific enough to test — pin a measurable condition and the next read can actually grade your call."

    if bucket == "dismissed":
        if claim_broke:
            return f"You dismissed an early warning tied to your “{claim_text or 'reason'}.” That reason later broke."
        return f"You dismissed “{bet}.” Nothing has followed through on it so far."

    if bucket == "exited":
        if breached:
            c = breached[0]
            return f"You exited {t} — “{bet}.” The break held up: {c['metric']} is {c['value_now']} vs your {c['operator']} {c['threshold']}."
        if held_all:
            return f"You exited {t} — “{bet}.” The condition you flagged has since recovered."
        if vague:
            return f"You exited {t} — “{bet}.” {weak_tail}"
        return f"You exited {t} — “{bet}.”" + (f" {phrase}." if phrase else "")

    # held
    if breached:
        c = breached[0]
        return f"You held {t} through “{bet}.” A condition you were watching has broken: {c['metric']} is {c['value_now']} vs your {c['operator']} {c['threshold']}."
    if held_all:
        return f"You held {t} through “{bet}.” The conditions you were watching still hold."
    if vague:
        return f"You held {t} through “{bet}.” {weak_tail}"
    return f"You held {t} through “{bet}.” No measurable condition has updated yet" + (f"; {phrase}." if phrase else ".")


async def resolve_snapshot(db: AsyncSession, snapshot: DecisionSnapshot, company_data, *, now: datetime) -> bool:
    """Compute and persist the read for one snapshot. Returns False (leaving it
    open to retry) if market data is unavailable."""
    if company_data is None or company_data.current_price is None:
        return False

    holding = (
        await db.execute(select(Holding).where(Holding.id == snapshot.holding_id))
    ).scalar_one_or_none()
    ticker = holding.ticker if holding else "?"

    conditions = _condition_reads(snapshot, company_data) if snapshot.bucket in ("held", "exited") else []
    price = _price_read(snapshot, company_data)
    if price.get("pct") is not None:
        bench_pct = await _benchmark_move_pct(snapshot)
        if bench_pct is not None:
            price["benchmark_ticker"] = snapshot.benchmark_ticker
            price["benchmark_pct"] = bench_pct
            price["relative_pct"] = round(price["pct"] - bench_pct, 1)
    claim_broke = await _claim_broke_after(db, snapshot) if snapshot.bucket == "dismissed" else None
    claim_text = await _claim_text(db, snapshot.claim_id) if claim_broke else None

    snapshot.resolved_at = now
    snapshot.resolution_json = {
        "resolution_kind": "earnings_test" if snapshot.next_test_at is not None else "soft_read",
        "price": price,
        "conditions": conditions,
        "claim_followthrough": (
            {"claim_id": str(snapshot.claim_id), "broke_after": claim_broke}
            if claim_broke is not None else None
        ),
        "read": _read_text(
            bucket=snapshot.bucket, ticker=ticker, bet=snapshot.bet_text,
            conditions=conditions, price=price, claim_broke=claim_broke, claim_text=claim_text,
            vague=_is_vague(snapshot),
        ),
    }
    return True


async def run_decision_resolution() -> None:
    """Daily job: resolve every open snapshot whose bet has now been tested.
    Batches one market-data fetch per ticker."""
    import time
    started = time.monotonic()
    logger.info("Starting decision resolution job")

    async with async_session() as db:
        now = datetime.now(timezone.utc)
        open_snaps = (
            await db.execute(select(DecisionSnapshot).where(DecisionSnapshot.resolved_at.is_(None)))
        ).scalars().all()
        ready = [s for s in open_snaps if is_ready(s, now)]
        if not ready:
            logger.info("Decision resolution: nothing ready")
            return

        holding_ids = {s.holding_id for s in ready}
        holdings = {
            h.id: h for h in (
                await db.execute(select(Holding).where(Holding.id.in_(holding_ids)))
            ).scalars().all()
        }
        by_ticker: dict[str, list[DecisionSnapshot]] = defaultdict(list)
        for s in ready:
            h = holdings.get(s.holding_id)
            if h:
                by_ticker[h.ticker].append(s)

        resolved = 0
        for ticker, group in by_ticker.items():
            try:
                company_data = await fetch_company_data(ticker)
            except Exception:
                logger.warning("Decision resolution: market data unavailable for %s", ticker, exc_info=True)
                company_data = None
            for snapshot in group:
                try:
                    if await resolve_snapshot(db, snapshot, company_data, now=now):
                        resolved += 1
                except Exception:
                    logger.exception("Decision resolution failed for snapshot %s", snapshot.id)

        await db.commit()

    logger.info("Decision resolution complete — %d resolved in %.1fs", resolved, time.monotonic() - started)
