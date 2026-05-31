from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.market_data import detect_native_currency, fetch_company_data, get_fx_rate
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.noise_filter import (
    apply_priority_suppression,
    filter_candidates,
)
from app.services.monitoring_pipeline import (
    build_claim_signal_lookup,
    classify_candidates_for_thesis,
    extract_news_watches,
    load_investor_profile,
    match_thesis_news_watches,
    persist_classified_candidates,
    signal_labels_from_claims,
)
from app.services.edgar import (
    build_edgar_candidates,
    build_form4_candidates,
    get_recent_8k_filings,
    get_recent_form4_transactions,
)
from app.services.edgar_extractor import enrich_earnings_candidates
from app.services.news_collector import collect_news_evidence
from app.services.signal_matching import (
    load_active_decomposition,
    match_candidates_to_signals,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_HOURS = 4


@dataclass
class MarketSnapshot:
    """Rich context returned even when no events fire."""
    current_price: float | None = None
    price_change_pct: float | None = None
    cost_basis: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    sector: str | None = None
    pe_ratio: float | None = None
    market_cap: float | None = None
    upcoming_earnings_date: datetime | None = None
    recent_news_count: int = 0
    watch_hints_ok: int = 0
    watch_hints_total: int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CheckNowResult:
    status: str  # completed | rate_limited | no_data
    events_created: int = 0
    next_available_at: datetime | None = None
    created_event_ids: list[uuid.UUID] = field(default_factory=list)
    snapshot: MarketSnapshot | None = None


async def _build_snapshot(
    company_data: "CompanyData | None",
    holding: Holding,
    previous_price: float | None,
    thesis: Thesis,
) -> MarketSnapshot:
    from app.services.market_data import CompanyData  # noqa: F811

    snapshot = MarketSnapshot()
    if company_data is None:
        return snapshot

    snapshot.current_price = company_data.current_price
    snapshot.sector = company_data.sector
    snapshot.pe_ratio = company_data.pe_ratio
    snapshot.market_cap = company_data.market_cap
    snapshot.upcoming_earnings_date = company_data.upcoming_earnings_date
    snapshot.recent_news_count = len(company_data.news_items)

    # Price change since last recorded price
    if company_data.current_price is not None and previous_price is not None and previous_price > 0:
        snapshot.price_change_pct = round(
            (company_data.current_price - previous_price) / previous_price * 100, 2
        )

    # P&L vs cost basis — average_cost_basis and current_value are stored in GBP
    # (account currency); current_price from market data is in native currency.
    # Convert current_price to GBP before computing P&L so both sides are the
    # same currency.
    cost_basis = float(holding.average_cost_basis)  # GBP
    snapshot.cost_basis = cost_basis
    if company_data.current_price is not None and cost_basis > 0:
        # current_price is quoted in the provider's currency, so that value is
        # the authoritative source for the conversion. Fall back to the stored
        # holding currency, then the ticker-suffix heuristic.
        native_ccy = company_data.currency or holding.currency or detect_native_currency(holding.ticker)
        fx_rate = await get_fx_rate(native_ccy, "GBP")
        total_cost = float(holding.quantity) * cost_basis
        total_value = float(holding.quantity) * company_data.current_price * fx_rate
        snapshot.pnl = round(total_value - total_cost, 2)
        snapshot.pnl_pct = round((total_value - total_cost) / total_cost * 100, 2)

    # Watch hint status
    market_values = {
        "revenue_growth_yoy": company_data.revenue_growth_yoy,
        "earnings_growth_yoy": company_data.earnings_growth_yoy,
        "pe_ratio": company_data.pe_ratio,
        "dividend_yield": company_data.dividend_yield,
    }
    market_values = {k: v for k, v in market_values.items() if v is not None}
    hint_results = check_metric_watch_hints(thesis.interpretation, market_values)
    snapshot.watch_hints_total = len(hint_results)
    snapshot.watch_hints_ok = sum(1 for r in hint_results if not r.breached)

    return snapshot


async def run_check_now(
    holding: Holding,
    thesis: Thesis,
    db: AsyncSession,
) -> CheckNowResult:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=RATE_LIMIT_HOURS)

    # Rate-limit check: any recent events (excluding monitoring_inactive)?
    recent_count = (
        await db.execute(
            select(func.count())
            .select_from(MonitoringEvent)
            .where(
                MonitoringEvent.holding_id == holding.id,
                MonitoringEvent.created_at >= cutoff,
                MonitoringEvent.event_type != "monitoring_inactive",
            )
        )
    ).scalar_one()

    if recent_count > 0:
        # Find when the earliest recent event was created to compute next_available_at
        earliest = (
            await db.execute(
                select(MonitoringEvent.created_at)
                .where(
                    MonitoringEvent.holding_id == holding.id,
                    MonitoringEvent.created_at >= cutoff,
                    MonitoringEvent.event_type != "monitoring_inactive",
                )
                .order_by(MonitoringEvent.created_at.asc())
                .limit(1)
            )
        ).scalar_one()
        next_available = earliest + timedelta(hours=RATE_LIMIT_HOURS)
        return CheckNowResult(status="rate_limited", next_available_at=next_available)

    # Fetch market data
    company_data = None
    try:
        company_data = await fetch_company_data(holding.ticker)
    except Exception:
        logger.exception("Failed to fetch market data for %s", holding.ticker)

    if company_data is None:
        logger.warning("No market data available for %s — skipping check", holding.ticker)
        return CheckNowResult(status="no_data")

    # Generate monitoring candidates
    previous_price = float(holding.current_price) if holding.current_price is not None else None
    candidates = generate_monitoring_candidates(
        thesis.interpretation,
        company_data,
        previous_price,
        now=now,
    )

    # EDGAR 8-K candidates (US tickers only; silently skipped for non-US)
    edgar_filings = await get_recent_8k_filings(holding.ticker)
    candidates.extend(build_edgar_candidates(holding.ticker, edgar_filings))

    # EDGAR Form 4 insider transactions
    form4_txns = await get_recent_form4_transactions(holding.ticker)
    candidates.extend(build_form4_candidates(holding.ticker, form4_txns, now=now))

    # Enrich earnings 8-Ks (item 2.02) with LLM-extracted content
    candidates = await enrich_earnings_candidates(candidates, thesis)

    # Signal linking: load decomposition and enrich candidates
    decomposition = await load_active_decomposition(db, thesis.id)
    claims = decomposition.claims if decomposition else None

    # Gemini news (uses signal labels from decomposition)
    signal_labels = signal_labels_from_claims(claims)
    gemini_candidates = await collect_news_evidence(
        holding.ticker, holding.name or holding.ticker, signal_labels
    )
    candidates.extend(gemini_candidates)
    candidates = match_candidates_to_signals(candidates, claims)

    # Build lookup tables for narrative generation
    claims_by_id, signals_by_id = build_claim_signal_lookup(claims)
    investor_profile = await load_investor_profile(db, thesis.user_id)

    # Build snapshot — always returned, even when 0 events
    snapshot = await _build_snapshot(company_data, holding, previous_price, thesis)

    # Update holding price
    if company_data and company_data.current_price is not None:
        holding.current_price = company_data.current_price
        holding.current_value = float(holding.quantity) * company_data.current_price

    # Record that we actually checked, even if the pass is quiet — this is what
    # lets the dashboard say "checked just now, all calm" truthfully.
    holding.last_monitored_at = now

    # Qualitative news_watch matching — BEFORE noise filtering, so a matched
    # news item is tagged (and survives minimum-relevance) and gets cooldown.
    nw_matched = await match_thesis_news_watches(candidates, extract_news_watches(claims))

    # Noise suppression: filter before classification (rules 1, 2, 4)
    candidates = await filter_candidates(candidates, holding.id, signals_by_id, db, now=now)

    classified = await classify_candidates_for_thesis(
        thesis,
        candidates,
        investor_profile=investor_profile,
        sector=holding.sector,
        ticker=holding.ticker,
        company_name=holding.name,
        nw_matched=nw_matched,
    )

    # Rule 3: Priority suppression (post-classification)
    suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
    surviving_set = {id(c) for c, _ in suppressed}
    classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]

    created_event_ids = await persist_classified_candidates(
        db,
        thesis=thesis,
        holding=holding,
        classified=classified,
        claims_by_id=claims_by_id,
        signals_by_id=signals_by_id,
        now=now,
        investor_profile=investor_profile,
    )

    await db.commit()

    return CheckNowResult(
        status="completed",
        events_created=len(created_event_ids),
        created_event_ids=created_event_ids,
        snapshot=snapshot,
    )


MONITORABLE_THESIS_STATUSES = ("active", "draft", "needs_review")
FIRST_PULSE_MAX_HOLDINGS = 5


async def _holdings_needing_first_pulse(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None,
    limit: int,
) -> list[tuple[Holding, Thesis]]:
    """Holdings that have a monitorable thesis but have never had a real
    monitoring pass yet (so the dashboard's 'all calm' has never actually been
    verified). Ordered by position size so the biggest bets get checked first."""
    event_exists = (
        select(MonitoringEvent.id)
        .where(
            MonitoringEvent.holding_id == Holding.id,
            MonitoringEvent.event_type != "monitoring_inactive",
        )
        .correlate(Holding)
        .limit(1)
    )
    query = (
        select(Holding)
        .where(Holding.user_id == user_id)
        .where(~event_exists.exists())
        .order_by(func.coalesce(Holding.current_value, 0).desc())
        .limit(limit)
    )
    if holding_id is not None:
        query = query.where(Holding.id == holding_id)

    holdings = (await db.execute(query)).scalars().all()

    pairs: list[tuple[Holding, Thesis]] = []
    for holding in holdings:
        thesis = (
            await db.execute(
                select(Thesis)
                .where(
                    Thesis.holding_id == holding.id,
                    Thesis.user_id == user_id,
                    Thesis.status.in_(MONITORABLE_THESIS_STATUSES),
                )
                .order_by(Thesis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if thesis is not None:
            pairs.append((holding, thesis))
    return pairs


async def _run_first_pulse_with_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None,
    limit: int,
) -> int:
    """Core of run_first_pulse, with an injected session so it's testable.
    Returns the number of holdings checked."""
    pairs = await _holdings_needing_first_pulse(
        db, user_id=user_id, holding_id=holding_id, limit=limit
    )
    checked = 0
    for holding, thesis in pairs:
        try:
            await run_check_now(holding, thesis, db)
            checked += 1
        except Exception:
            # One holding failing (bad ticker, market data outage) must not stop
            # the rest — the first pulse is best-effort.
            logger.exception("First pulse: check failed for holding %s", holding.id)
    return checked


async def run_first_pulse(
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None = None,
    *,
    limit: int = FIRST_PULSE_MAX_HOLDINGS,
) -> None:
    """Run the first monitoring pass the moment a thesis becomes monitorable.

    Without this, a new user who just wrote their theses sees a dashboard that
    reports every position as "intact — your assumptions still hold" when nothing
    has actually been checked (monitoring events only appear after the next 6 AM
    job). This delivers a truthful first pulse in their very first session: a live
    snapshot plus any price/news/earnings/filing signal that already contradicts
    the thesis.

    Designed as a FastAPI BackgroundTask: opens its own DB session (like
    generate_draft_theses_for_user), is idempotent (skips any holding that already
    has a real monitoring event), and never raises.
    """
    if not settings.enable_first_pulse:
        return

    from app.database import async_session

    try:
        async with async_session() as db:
            await _run_first_pulse_with_session(
                db, user_id=user_id, holding_id=holding_id, limit=limit
            )
    except Exception:
        logger.exception("First pulse failed for user %s", user_id)
