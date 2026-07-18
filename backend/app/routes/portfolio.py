import uuid
from datetime import datetime, time, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.limiter import limiter
from app.database import get_db
from app.config import settings
from app.dependencies import get_current_user
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.broker_connection import ConnectBrokerRequest, BrokerConnectionResponse
from app.schemas.onboarding import DraftItemResponse, DraftStatusResponse
from app.schemas.holding import (
    ConvictionLogEntryResponse,
    ConvictionLogResponse,
    HoldingResponse,
    ManualHoldingRequest,
    ManualNoteRequest,
    PortfolioPulseResponse,
    PortfolioSummary,
    PortfolioTrendResponse,
    PriorityHoldingSummary,
    SimulateTradeRequest,
    SimulateTradeResponse,
    UpcomingEarningsResponse,
)
from app.services.encryption import encrypt, decrypt
from app.services.trading212 import Trading212Client, build_auth_header, detect_trading212_base_url, normalise_t212_ticker
from app.services.csv_parser import parse_csv_detailed
from app.services.market_data import detect_native_currency, fetch_company_data, fetch_company_overview, fetch_live_price, get_fx_rate
from app.services.valuation import apply_broker_position, refresh_holding_price, to_account_value

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
_REAL_DATETIME = datetime


async def _enrich_holding_metadata(
    ticker: str,
    *,
    name: str,
    sector: str | None = None,
    geography: str | None = None,
    currency: str | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    """Resolve name/sector/geography/native currency from the market data
    provider so a manual or CSV import matches what broker sync produces. The
    provider is authoritative on currency (otherwise US stocks imported without
    a currency column get valued as GBP — a large silent error). Existing
    descriptive values win over provider defaults."""
    enriched_name = name
    enriched_sector = sector
    enriched_geography = geography
    native_currency = currency
    try:
        overview = await fetch_company_overview(ticker)
        if overview:
            if not enriched_sector and overview["sector"] != "Unknown":
                enriched_sector = overview["sector"]
            if not enriched_geography and overview["country"] != "Unknown":
                enriched_geography = overview["country"]
            if enriched_name == ticker and overview["name"] != ticker:
                enriched_name = overview["name"]
            if overview.get("currency"):
                native_currency = overview["currency"]
    except Exception:
        pass
    return enriched_name, enriched_sector, enriched_geography, native_currency


@router.get("/search")
@limiter.limit("30/minute")
async def search_tickers(request: Request, q: str):
    """Proxy Yahoo Finance ticker search for the manual add holding flow."""
    if not q or len(q.strip()) < 1:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://query2.finance.yahoo.com/v1/finance/search",
                params={"q": q, "quotesCount": 10, "newsCount": 0, "enableFuzzyQuery": "false"},
                headers={"User-Agent": "Mozilla/5.0"},
            )
        if not r.is_success:
            return []
        quotes = r.json().get("quotes", [])
        return [
            {
                "ticker": item["symbol"],
                "name": item.get("longname") or item.get("shortname") or item["symbol"],
                "exchange": item.get("exchange", ""),
            }
            for item in quotes
            if item.get("quoteType") in ("EQUITY", "ETF")
        ][:8]
    except Exception:
        return []


def _age_in_days(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - normalized).days


def _days_until(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (normalized.date() - datetime.now(timezone.utc).date()).days


def _holding_value(holding: Holding) -> float:
    cost = float(holding.quantity) * float(holding.average_cost_basis)
    return float(holding.current_value) if holding.current_value is not None else cost


def _is_monitorable(thesis: Thesis | None) -> bool:
    if thesis is None or thesis.status not in {"draft", "active", "needs_review"}:
        return False

    interpretation = thesis.interpretation or {}
    monitorability = interpretation.get("monitorability")
    if monitorability in {"high", "medium"}:
        return True

    watch_hints = interpretation.get("watch_hints")
    if isinstance(watch_hints, list) and len(watch_hints) > 0:
        return True

    if thesis.must_remain_true and thesis.what_would_change_my_mind:
        return True

    return False


def _priority_reason(holding: Holding, thesis: Thesis | None, thesis_age_days: int | None) -> tuple[str, str] | None:
    if thesis is None or thesis.status not in {"draft", "active", "needs_review"}:
        return ("critical", "No active thesis yet for this position.")

    if thesis.status == "needs_review":
        return ("high", "This thesis has been flagged for review.")

    if thesis_age_days is not None and thesis_age_days > 90:
        return ("high", "This thesis is stale and has not been reviewed in over 90 days.")

    if not _is_monitorable(thesis):
        return ("medium", "This reason is too vague to monitor well.")

    if thesis.confidence == "low":
        return ("medium", "Position size may not match your stated confidence.")

    return None


def _requires_market_data_key() -> bool:
    return settings.market_data_provider == "alpha_vantage"


def _monitoring_status_message(*, holdings_with_current_theses_count: int) -> tuple[bool, str]:
    monitoring_ready = bool(
        settings.enable_scheduler
        and (not _requires_market_data_key() or settings.alpha_vantage_api_key)
    )
    if not settings.enable_scheduler:
        return False, "Monitoring is disabled in this environment."
    if _requires_market_data_key() and not settings.alpha_vantage_api_key:
        return False, "Monitoring is not active yet. Add ALPHA_VANTAGE_API_KEY to enable daily portfolio monitoring."
    if holdings_with_current_theses_count == 0:
        return monitoring_ready, "Monitoring is on, but we need at least one written thesis before there's anything to compare news against."
    return monitoring_ready, "We check your theses each morning and email a weekly digest on Sunday."


@router.post("/connect", response_model=BrokerConnectionResponse, status_code=status.HTTP_201_CREATED)
async def connect_broker(
    body: ConnectBrokerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.broker_type != "trading212":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only trading212 is supported")

    auth_header = build_auth_header(body.api_key, body.api_secret)
    base_url = await detect_trading212_base_url(auth_header)
    if base_url is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials not accepted by Trading 212. Check you copied the full key and secret, and that they're from the correct account (live or practice).",
        )

    encrypted_key = encrypt(f"{base_url}\n{auth_header}")
    connection = BrokerConnection(
        user_id=current_user.id,
        broker_type=body.broker_type,
        encrypted_api_key=encrypted_key,
        status="active",
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.post("/sync/{connection_id}", response_model=list[HoldingResponse])
async def sync_broker(
    connection_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.user_id == current_user.id,
        )
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    stored = decrypt(connection.encrypted_api_key)
    if "\n" in stored:
        base_url, auth_header = stored.split("\n", 1)
    else:
        # Legacy records stored only the auth header; re-probe once to find the URL.
        auth_header = stored
        base_url = await detect_trading212_base_url(auth_header)
        if base_url is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Trading 212 credentials are no longer valid. Reconnect your account.",
            )
    client = Trading212Client(auth_header=auth_header, base_url=base_url)
    try:
        positions = await client.fetch_positions()
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trading 212 credentials are no longer valid. Reconnect your account.",
        )

    if not positions:
        logger.warning("Trading212 sync returned 0 positions for connection %s — portfolio may be empty or API permissions insufficient", connection.id)

    synced_holdings = []
    for pos in positions:
        pos.ticker = normalise_t212_ticker(pos.ticker)
        existing_result = await db.execute(
            select(Holding).where(
                Holding.user_id == current_user.id,
                Holding.ticker == pos.ticker,
            )
        )
        holding = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if holding is None:
            # Enrich new holdings with sector/geography from market data
            h_sector = None
            h_geography = None
            h_name = pos.ticker
            try:
                overview = await fetch_company_overview(pos.ticker)
                if overview:
                    h_sector = overview["sector"] if overview["sector"] != "Unknown" else None
                    h_geography = overview["country"] if overview["country"] != "Unknown" else None
                    h_name = overview["name"] if overview["name"] != pos.ticker else pos.ticker
            except Exception:
                logger.warning("Failed to enrich sector/geography for %s", pos.ticker, exc_info=True)

            holding = Holding(
                user_id=current_user.id,
                broker_connection_id=connection.id,
                ticker=pos.ticker.upper(),
                name=h_name,
                quantity=pos.quantity,
                average_cost_basis=pos.average_price,  # set to GBP by apply_broker_position below
                sector=h_sector,
                geography=h_geography,
            )
            db.add(holding)
        else:
            # Backfill sector/geography if missing
            if not holding.sector or not holding.geography:
                try:
                    overview = await fetch_company_overview(pos.ticker)
                    if overview:
                        if not holding.sector and overview["sector"] != "Unknown":
                            holding.sector = overview["sector"]
                        if not holding.geography and overview["country"] != "Unknown":
                            holding.geography = overview["country"]
                        if holding.name == pos.ticker and overview["name"] != pos.ticker:
                            holding.name = overview["name"]
                except Exception:
                    logger.warning("Failed to backfill sector/geography for %s", pos.ticker, exc_info=True)

        # Convert the broker's native-currency price + cost into GBP (single path).
        await apply_broker_position(
            holding,
            quantity=pos.quantity,
            native_price=pos.current_price,
            native_avg_cost=pos.average_price,
            now=now,
        )
        synced_holdings.append(holding)

    connection.last_synced_at = datetime.now(timezone.utc)
    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()

    for h in synced_holdings:
        await db.refresh(h)

    # No auto-drafting a thesis on import. The product leads with the user's own
    # words (onboarding asks them first); AI drafting is now an explicit opt-in,
    # so we never pre-write a reason before they've had their turn.
    return synced_holdings


@router.get("/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding)
        .where(Holding.user_id == current_user.id)
        .order_by(Holding.current_value.desc().nulls_last())
    )
    holdings = result.scalars().all()
    return holdings


@router.get("/holdings/unthesised", response_model=list[HoldingResponse])
async def list_unthesised_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = holdings_result.scalars().all()

    if not holdings:
        return []

    holding_ids = [h.id for h in holdings]
    theses_result = await db.execute(
        select(Thesis.holding_id)
        .where(
            Thesis.holding_id.in_(holding_ids),
            Thesis.user_id == current_user.id,
            Thesis.status.in_(["draft", "active", "needs_review"]),
        )
        .distinct()
    )
    holdings_with_thesis = {row[0] for row in theses_result.all()}

    unthesised = [h for h in holdings if h.id not in holdings_with_thesis]
    unthesised.sort(key=_holding_value, reverse=True)
    return unthesised


@router.post("/holdings", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
async def add_manual_holding(
    body: ManualHoldingRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(Holding).where(
            Holding.user_id == current_user.id,
            Holding.ticker == body.ticker.upper(),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{body.ticker.upper()} is already in your portfolio.",
        )

    enriched_name, enriched_sector, enriched_geography, native_currency = await _enrich_holding_metadata(
        body.ticker,
        name=body.name,
        sector=body.sector,
        geography=body.geography,
        currency=body.currency,
    )

    holding = Holding(
        user_id=current_user.id,
        ticker=body.ticker.upper(),
        name=enriched_name,
        exchange=body.exchange,
        sector=enriched_sector,
        geography=enriched_geography,
        asset_class=body.asset_class,
    )
    db.add(holding)

    # The entered average cost is in the instrument's native currency; convert it to
    # the account currency (GBP) and keep the native figure for display. Mirrors the
    # broker-sync and CSV paths so valuation is consistent everywhere.
    await apply_broker_position(
        holding,
        quantity=body.quantity,
        native_price=None,
        native_avg_cost=body.average_cost_basis,
        native_currency=native_currency,
    )
    await db.flush()

    # Fetch a live price now so a manually-added position shows a real value
    # immediately, instead of £0.00 / -100% until the next background sync.
    try:
        await refresh_holding_price(holding)
    except Exception:
        logger.warning("Could not fetch initial price for %s", holding.ticker, exc_info=True)

    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()
    await db.refresh(holding)

    # No auto-draft on import — the user writes their own reason; AI help is opt-in.
    return holding


@router.post("/holdings/enrich", response_model=list[HoldingResponse])
async def enrich_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backfill sector/geography and fix mislabelled currency for all holdings.

    Also repairs holdings created before currency was provider-resolved: a US stock
    added by bare ticker was tagged GBP with its native price/cost written straight
    into the GBP fields (no FX). When the provider reports a different currency, we
    treat the stored figures as native and renormalise to the account currency.
    """
    result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = result.scalars().all()
    updated = []

    for h in holdings:
        try:
            overview = await fetch_company_overview(h.ticker)
            if not overview:
                continue
            changed = False
            if not h.sector and overview["sector"] != "Unknown":
                h.sector = overview["sector"]
                changed = True
            if not h.geography and overview["country"] != "Unknown":
                h.geography = overview["country"]
                changed = True
            if h.name == h.ticker and overview["name"] != h.ticker:
                h.name = overview["name"]
                changed = True

            provider_ccy = overview.get("currency")
            if provider_ccy and provider_ccy != h.currency:
                # Currency was mislabelled. The stored avg/value were never FX-converted,
                # so treat the stored cost as the native figure and renormalise.
                native_avg = float(h.average_cost_native if h.average_cost_native is not None else h.average_cost_basis)
                await apply_broker_position(
                    h,
                    quantity=h.quantity,
                    native_price=None,
                    native_avg_cost=native_avg,
                    native_currency=provider_ccy,
                )
                try:
                    await refresh_holding_price(h)
                except Exception:
                    logger.warning("Could not refresh price for %s during enrich", h.ticker, exc_info=True)
                changed = True

            if changed:
                updated.append(h)
        except Exception:
            continue

    await db.commit()
    for h in updated:
        await db.refresh(h)
    return updated


@router.post("/upload-csv", response_model=list[HoldingResponse], status_code=status.HTTP_201_CREATED)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    parsed, diag = parse_csv_detailed(text)
    if not parsed:
        if diag.skipped_bad_numbers > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Found {diag.skipped_bad_numbers} row(s), but couldn't read the quantity or "
                    "average cost as numbers. Check those columns hold plain numbers (no currency "
                    "symbols or commas)."
                ),
            )
        raise HTTPException(status_code=400, detail="No holdings found in CSV. Check the format.")

    now = datetime.now(timezone.utc)
    created = []
    for p in parsed:
        # Upsert: update if ticker already exists for this user
        existing_result = await db.execute(
            select(Holding).where(
                Holding.user_id == current_user.id,
                Holding.ticker == p.ticker,
            )
        )
        holding = existing_result.scalar_one_or_none()

        # Ask the provider for the authoritative currency (and enrich sector /
        # geography while we're at it). Generic CSVs rarely include a currency
        # column, so parse_generic_csv defaults them to GBP — writing a US stock
        # into current_value at £USD is the same silent FX bug portfolio_sync
        # used to have. Trading 212 exports already carry the correct currency,
        # so the provider only overrides when we're confident.
        enriched_name, enriched_sector, enriched_geography, native_currency = await _enrich_holding_metadata(
            p.ticker,
            name=p.name,
            currency=p.currency,
        )

        if holding:
            holding.name = enriched_name
            if enriched_sector:
                holding.sector = enriched_sector
            if enriched_geography:
                holding.geography = enriched_geography
        else:
            holding = Holding(
                user_id=current_user.id,
                ticker=p.ticker.upper(),
                name=enriched_name,
                sector=enriched_sector,
                geography=enriched_geography,
            )
            db.add(holding)

        # Normalise valuation to the account currency (GBP), like broker sync.
        # apply_broker_position converts the cost basis; refresh_holding_price
        # fetches a live price for current_value.
        await apply_broker_position(
            holding,
            quantity=p.quantity,
            native_price=None,
            native_avg_cost=p.average_cost_basis,
            native_currency=native_currency,
            now=now,
        )
        try:
            await refresh_holding_price(holding, now=now)
        except Exception:
            logger.warning("Could not fetch initial price for %s", holding.ticker, exc_info=True)

        created.append(holding)

    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()
    for h in created:
        await db.refresh(h)

    # No auto-draft on import — the user writes their own reason; AI help is opt-in.
    return created


@router.get("/live-prices")
async def live_prices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return fresh market prices for all holdings, bypassing the DB snapshot.

    Prices are fetched via yfinance fast_info (60s cache) and converted to GBP.
    The frontend overlays these on top of the stored values so the display stays
    current without a full T212 sync.
    """
    result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = result.scalars().all()

    import asyncio as _asyncio

    async def _price_for(holding: Holding) -> dict:
        price = await fetch_live_price(holding.ticker)
        if price is None or price <= 0:
            return {"ticker": holding.ticker, "current_price": None, "current_value": None}
        current_value_gbp = await to_account_value(
            holding.quantity, price, native_currency=holding.currency, ticker=holding.ticker
        )
        return {
            "ticker": holding.ticker,
            "current_price": price,
            "current_value": current_value_gbp,
        }

    prices = await _asyncio.gather(*[_price_for(h) for h in holdings])
    return [p for p in prices if p["current_price"] is not None]


@router.get("/pulse", response_model=PortfolioPulseResponse)
async def portfolio_pulse(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.pulse import compute_portfolio_pulse

    pulses, next_digest_at = await compute_portfolio_pulse(current_user.id, db)
    return PortfolioPulseResponse(
        pulses=[
            {
                "holding_id": p.holding_id,
                "ticker": p.ticker,
                "name": p.name,
                "pulse_status": p.pulse_status,
                "pulse_basis": p.pulse_basis,
                "reason": p.reason,
                "assumption_label": p.assumption_label,
                "latest_event_summary": p.latest_event_summary,
                "days_since_thesis_update": p.days_since_thesis_update,
                "has_thesis": p.has_thesis,
                "latest_event_at": p.latest_event_at,
                "urgency_score": p.urgency_score,
                "pnl_pct": p.pnl_pct,
                "last_checked_at": p.last_checked_at,
                "recent_event_count": p.recent_event_count,
                "unresolved_event_count": p.unresolved_event_count,
                "sources_count": p.sources_count,
            }
            for p in pulses
        ],
        next_digest_at=next_digest_at,
    )


@router.get("/draft-status", response_model=DraftStatusResponse)
async def draft_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from collections import Counter
    from app.models.onboarding_draft import OnboardingDraft

    result = await db.execute(
        select(OnboardingDraft, Holding, Thesis)
        .join(Holding, OnboardingDraft.holding_id == Holding.id)
        .outerjoin(Thesis, OnboardingDraft.thesis_id == Thesis.id)
        .where(OnboardingDraft.user_id == current_user.id)
        .order_by(OnboardingDraft.created_at.desc())
        .limit(50)
    )
    rows = result.all()

    drafts = [
        DraftItemResponse(
            draft_id=draft.id,
            holding_id=draft.holding_id,
            ticker=holding.ticker,
            name=holding.name,
            status=draft.status,
            thesis_id=draft.thesis_id,
            why_own_it=thesis.why_own_it if thesis else None,
            must_remain_true=thesis.must_remain_true if thesis else None,
            what_would_change_my_mind=thesis.what_would_change_my_mind if thesis else None,
        )
        for draft, holding, thesis in rows
    ]

    counts = Counter(d.status for d in drafts)
    return DraftStatusResponse(
        total=len(drafts),
        ready=counts["ready"],
        pending=counts["pending"],
        failed=counts["failed"],
        reviewed=counts["reviewed"],
        drafts=drafts,
    )


@router.get("/upcoming-earnings", response_model=list[UpcomingEarningsResponse])
async def upcoming_earnings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holdings_result = await db.execute(
        select(Holding)
        .where(Holding.user_id == current_user.id)
        .order_by(Holding.current_value.desc().nulls_last())
    )
    holdings = holdings_result.scalars().all()
    if not holdings:
        return []

    from app.services.earnings_service import get_or_refresh_earnings

    upcoming: list[UpcomingEarningsResponse] = []
    for holding in holdings:
        try:
            report_date = await get_or_refresh_earnings(db, holding.ticker)
        except Exception:
            continue

        if report_date is None:
            continue

        days_until = _days_until(report_date)
        if days_until < 0:
            continue  # Already passed

        upcoming.append(
            UpcomingEarningsResponse(
                holding_id=holding.id,
                ticker=holding.ticker,
                name=holding.name,
                report_date=report_date,
                days_until=days_until,
            )
        )

    await db.commit()
    upcoming.sort(key=lambda item: item.report_date)
    return upcoming[:10]


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == current_user.id)
    )
    holdings = holdings_result.scalars().all()

    total_value = 0.0
    total_cost = 0.0
    sector_totals: dict[str, float] = {}
    geography_totals: dict[str, float] = {}

    holding_ids = []
    holdings_with_current_theses = set()
    theses_active = 0
    theses_need_review = 0
    stale_theses_count = 0
    thesis_coverage_value = 0.0
    monitorable_coverage_value = 0.0
    attention_candidates: list[tuple[int, float, PriorityHoldingSummary]] = []
    latest_by_holding: dict[uuid.UUID, Thesis] = {}
    holdings_by_id = {holding.id: holding for holding in holdings}

    for h in holdings:
        cost = float(h.quantity) * float(h.average_cost_basis)
        value = _holding_value(h)
        total_cost += cost
        total_value += value

        sector = h.sector or "Unknown"
        geography = h.geography or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value
        geography_totals[geography] = geography_totals.get(geography, 0.0) + value

        holding_ids.append(h.id)

    if holding_ids:
        theses_result = await db.execute(
            select(Thesis).where(
                Thesis.holding_id.in_(holding_ids),
                Thesis.user_id == current_user.id,
            )
            .order_by(Thesis.created_at.desc())
        )
        theses = theses_result.scalars().all()

        for thesis in theses:
            latest_by_holding.setdefault(thesis.holding_id, thesis)

        for thesis in latest_by_holding.values():
            if thesis.status in {"draft", "active", "needs_review"}:
                holdings_with_current_theses.add(thesis.holding_id)
                matched_holding = holdings_by_id.get(thesis.holding_id)
                if matched_holding is not None:
                    thesis_coverage_value += _holding_value(matched_holding)
                    if _is_monitorable(thesis):
                        monitorable_coverage_value += _holding_value(matched_holding)
            thesis_age_days = _age_in_days(thesis.updated_at)
            if thesis.status == "active" and thesis_age_days <= 90:
                theses_active += 1
            elif thesis.status == "needs_review" or (
                thesis.status in {"draft", "active"} and thesis_age_days > 90
            ):
                theses_need_review += 1
            if thesis.status in {"draft", "active", "needs_review"} and thesis_age_days > 90:
                stale_theses_count += 1

    theses_missing = len(holdings) - len(holdings_with_current_theses)
    unmonitored_holdings_count = 0
    conviction_mismatch_count = 0

    sorted_holdings = sorted(holdings, key=_holding_value, reverse=True)
    top_3_value = sum(_holding_value(holding) for holding in sorted_holdings[:3])
    top_3_concentration_pct = round((top_3_value / total_value * 100), 2) if total_value > 0 else 0.0

    for index, holding in enumerate(sorted_holdings):
        thesis = latest_by_holding.get(holding.id)
        if not _is_monitorable(thesis):
            unmonitored_holdings_count += 1
        if index < 3 and (thesis is None or thesis.confidence == "low" or not _is_monitorable(thesis)):
            conviction_mismatch_count += 1

        thesis_age_days = _age_in_days(thesis.updated_at) if thesis is not None else None
        priority = _priority_reason(holding, thesis, thesis_age_days)
        if priority is None:
            continue
        priority_label, reason = priority
        score = {"critical": 3, "high": 2, "medium": 1}[priority_label]
        attention_candidates.append(
            (
                score,
                _holding_value(holding),
                PriorityHoldingSummary(
                    holding_id=holding.id,
                    ticker=holding.ticker,
                    name=holding.name,
                    reason=reason,
                    priority=priority_label,
                ),
            )
        )

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    def to_pct(totals: dict[str, float]) -> dict[str, float]:
        grand = sum(totals.values())
        if grand == 0:
            return {k: 0.0 for k in totals}
        return {k: round(v / grand * 100, 2) for k, v in totals.items()}

    attention_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    attention_queue = [item[2] for item in attention_candidates[:3]]
    monitoring_ready, monitoring_message = _monitoring_status_message(
        holdings_with_current_theses_count=len(holdings_with_current_theses),
    )

    thesis_cov = round((thesis_coverage_value / total_value * 100), 2) if total_value > 0 else 0.0
    monitorable_cov = round((monitorable_coverage_value / total_value * 100), 2) if total_value > 0 else 0.0

    # Lazy snapshot: create one per user per day
    from app.models.portfolio_snapshot import PortfolioSnapshot
    today = datetime.now(timezone.utc).date()
    existing_snap = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == current_user.id,
            PortfolioSnapshot.snapshot_date == today,
        )
    )
    if existing_snap.scalar_one_or_none() is None and len(holdings) > 0:
        snap = PortfolioSnapshot(
            user_id=current_user.id,
            snapshot_date=today,
            total_value=total_value,
            total_cost=total_cost,
            top_3_concentration_pct=top_3_concentration_pct,
            thesis_coverage_pct=thesis_cov,
            monitorable_pct=monitorable_cov,
            unmonitored_count=unmonitored_holdings_count,
            holdings_count=len(holdings),
        )
        db.add(snap)
        try:
            await db.commit()
        except Exception:
            await db.rollback()

    return PortfolioSummary(
        total_value=total_value,
        total_cost=total_cost,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        holdings_count=len(holdings),
        theses_active=theses_active,
        theses_need_review=theses_need_review,
        theses_missing=theses_missing,
        top_3_concentration_pct=top_3_concentration_pct,
        thesis_coverage_pct=thesis_cov,
        monitorable_thesis_coverage_pct=monitorable_cov,
        stale_theses_count=stale_theses_count,
        unmonitored_holdings_count=unmonitored_holdings_count,
        conviction_mismatch_count=conviction_mismatch_count,
        monitoring_ready=monitoring_ready,
        monitoring_message=monitoring_message,
        sector_breakdown=to_pct(sector_totals),
        geography_breakdown=to_pct(geography_totals),
        attention_queue=attention_queue,
    )


@router.get("/summary/trend", response_model=PortfolioTrendResponse)
async def portfolio_trend(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.portfolio_snapshot import PortfolioSnapshot
    today = datetime.now(timezone.utc).date()
    result = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == current_user.id,
            PortfolioSnapshot.snapshot_date < today,
        ).order_by(PortfolioSnapshot.snapshot_date.desc()).limit(1)
    )
    snap = result.scalar_one_or_none()
    if snap is None:
        return PortfolioTrendResponse()
    from app.models.monitoring_event import MonitoringEvent

    snapshot_start = _REAL_DATETIME.combine(snap.snapshot_date, time.min, tzinfo=timezone.utc)
    active_thesis_ids = select(Thesis.id).where(
        Thesis.user_id == current_user.id,
        Thesis.status.in_(["active", "draft", "needs_review"]),
    )
    event_count = await db.scalar(
        select(func.count(MonitoringEvent.id)).where(
            MonitoringEvent.thesis_id.in_(active_thesis_ids),
            MonitoringEvent.created_at >= snapshot_start,
        )
    )
    return PortfolioTrendResponse(
        snapshot_date=snap.snapshot_date.isoformat(),
        new_event_count=event_count or 0,
        top_3_concentration_pct=float(snap.top_3_concentration_pct),
        thesis_coverage_pct=float(snap.thesis_coverage_pct),
        monitorable_pct=float(snap.monitorable_pct),
        unmonitored_count=snap.unmonitored_count,
        holdings_count=snap.holdings_count,
    )


@router.post("/simulate", response_model=SimulateTradeResponse)
async def simulate_trade(
    body: SimulateTradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.simulation import simulate_trade as run_simulation

    result = await run_simulation(
        user_id=current_user.id,
        ticker=body.ticker,
        quantity=body.quantity,
        price_per_share=body.price_per_share,
        db=db,
    )
    return SimulateTradeResponse(
        ticker=result.ticker,
        name=result.name,
        simulated_quantity=result.simulated_quantity,
        simulated_price=result.simulated_price,
        simulated_value=result.simulated_value,
        before={
            "total_value": result.before.total_value,
            "total_cost": result.before.total_cost,
            "holdings_count": result.before.holdings_count,
            "top_3_concentration_pct": result.before.top_3_concentration_pct,
            "sector_breakdown": result.before.sector_breakdown,
        },
        after={
            "total_value": result.after.total_value,
            "total_cost": result.after.total_cost,
            "holdings_count": result.after.holdings_count,
            "top_3_concentration_pct": result.after.top_3_concentration_pct,
            "sector_breakdown": result.after.sector_breakdown,
        },
        warnings=[
            {"warning_type": w.warning_type, "message": w.message}
            for w in result.warnings
        ],
    )


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == current_user.id)
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    from app.models.monitoring_event import MonitoringEvent
    from app.models.conviction_log_entry import ConvictionLogEntry
    from app.models.quarterly_review_response import QuarterlyReviewResponse

    # Delete in dependency order; Thesis/MonitoringEvent sub-relations cascade automatically
    for model, col in [
        (QuarterlyReviewResponse, QuarterlyReviewResponse.holding_id),
        (MonitoringEvent, MonitoringEvent.holding_id),
        (ConvictionLogEntry, ConvictionLogEntry.holding_id),
    ]:
        rows = await db.execute(select(model).where(col == holding_id))
        for row in rows.scalars().all():
            await db.delete(row)

    theses = await db.execute(select(Thesis).where(Thesis.holding_id == holding_id))
    for thesis in theses.scalars().all():
        await db.delete(thesis)

    await db.delete(holding)
    await db.commit()


@router.get("/holdings/{holding_id}/conviction-log", response_model=ConvictionLogResponse)
async def get_conviction_log(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.conviction_log_entry import ConvictionLogEntry
    from app.models.decision_snapshot import DecisionSnapshot
    from app.models.monitoring_event import MonitoringEvent
    from app.services.conviction_log import EVIDENCE_REVIEWED, POST_EARNINGS_REVIEW, QUARTERLY_REVIEW

    # Verify holding belongs to user
    holding_result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == current_user.id)
    )
    holding = holding_result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    # Fetch all entries, newest first
    entries_result = await db.execute(
        select(ConvictionLogEntry)
        .where(ConvictionLogEntry.holding_id == holding_id)
        .order_by(ConvictionLogEntry.created_at.desc())
    )
    entries = entries_result.scalars().all()

    # Collect event IDs and thesis IDs from evidence_reviewed entries only
    parsed_event_ids: dict[str, uuid.UUID] = {}
    evidence_thesis_ids: set[uuid.UUID] = set()
    for e in entries:
        if e.entry_type == EVIDENCE_REVIEWED and e.metadata_json:
            eid = e.metadata_json.get("event_id")
            if eid and eid not in parsed_event_ids:
                try:
                    parsed_event_ids[eid] = uuid.UUID(eid)
                except ValueError:
                    pass
            if e.thesis_id:
                evidence_thesis_ids.add(e.thesis_id)

    # Load monitoring events in bulk
    events_by_id: dict[uuid.UUID, MonitoringEvent] = {}
    if parsed_event_ids:
        events_result = await db.execute(
            select(MonitoringEvent).where(MonitoringEvent.id.in_(parsed_event_ids.values()))
        )
        events_by_id = {ev.id: ev for ev in events_result.scalars().all()}

    # Load only theses needed for evidence_reviewed enrichment
    theses_by_id: dict[uuid.UUID, Thesis] = {}
    if evidence_thesis_ids:
        theses_result = await db.execute(
            select(Thesis).where(Thesis.id.in_(evidence_thesis_ids))
        )
        theses_by_id = {t.id: t for t in theses_result.scalars().all()}

    # Load resolved DecisionSnapshots for this holding to surface read-back text
    resolved_reads: dict[uuid.UUID, str] = {}  # monitoring_event_id -> resolution read
    if parsed_event_ids:
        snaps_result = await db.execute(
            select(DecisionSnapshot).where(
                DecisionSnapshot.holding_id == holding_id,
                DecisionSnapshot.monitoring_event_id.in_(parsed_event_ids.values()),
                DecisionSnapshot.resolved_at.is_not(None),
            )
        )
        for snap in snaps_result.scalars().all():
            if snap.monitoring_event_id and snap.resolution_json:
                read = snap.resolution_json.get("read")
                if read:
                    resolved_reads[snap.monitoring_event_id] = read

    # Compute reason age: days since first reason_created entry (fall back to earliest thesis)
    reason_age_days = None
    for entry in reversed(entries):
        if entry.entry_type == "reason_created":
            reason_age_days = _age_in_days(entry.created_at)
            break
    if reason_age_days is None:
        earliest_thesis_result = await db.execute(
            select(Thesis.created_at)
            .where(Thesis.holding_id == holding_id)
            .order_by(Thesis.created_at.asc())
            .limit(1)
        )
        earliest_thesis_date = earliest_thesis_result.scalar_one_or_none()
        if earliest_thesis_date is not None:
            reason_age_days = _age_in_days(earliest_thesis_date)

    review_types = {EVIDENCE_REVIEWED, POST_EARNINGS_REVIEW, QUARTERLY_REVIEW}
    review_count = sum(1 for e in entries if e.entry_type in review_types)

    # Build enriched entry responses
    enriched: list[ConvictionLogEntryResponse] = []
    for e in entries:
        extra: dict = {}
        if e.entry_type == EVIDENCE_REVIEWED and e.metadata_json:
            eid_str = e.metadata_json.get("event_id")
            if eid_str:
                event_uuid = parsed_event_ids.get(eid_str)
                event = events_by_id.get(event_uuid) if event_uuid else None
                if event:
                    extra["event_title"] = event.title
                    extra["event_severity"] = event.severity
                if event_uuid and event_uuid in resolved_reads:
                    extra["resolution_read"] = resolved_reads[event_uuid]
            thesis = theses_by_id.get(e.thesis_id) if e.thesis_id else None
            if thesis:
                extra["what_would_change_my_mind"] = thesis.what_would_change_my_mind
                if thesis.status == "invalidated":
                    extra["outcome"] = "broke"
                elif thesis.status in ("active", "needs_review"):
                    extra["outcome"] = "held"
        base = ConvictionLogEntryResponse.model_validate(e, from_attributes=True)
        enriched.append(base.model_copy(update=extra) if extra else base)

    return ConvictionLogResponse(
        entries=enriched,
        reason_age_days=reason_age_days,
        review_count=review_count,
    )


@router.post(
    "/holdings/{holding_id}/conviction-log",
    response_model=ConvictionLogEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_manual_note(
    holding_id: uuid.UUID,
    body: ManualNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.conviction_log import MANUAL_NOTE, append_log_entry

    # Verify holding belongs to user
    holding_result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == current_user.id)
    )
    holding = holding_result.scalar_one_or_none()
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    # Need a thesis for this holding
    thesis_result = await db.execute(
        select(Thesis).where(
            Thesis.holding_id == holding_id,
            Thesis.user_id == current_user.id,
            Thesis.status.in_(["draft", "active", "needs_review"]),
        ).order_by(Thesis.created_at.desc()).limit(1)
    )
    thesis = thesis_result.scalar_one_or_none()
    if thesis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active thesis for this holding")

    entry = append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=current_user.id,
        entry_type=MANUAL_NOTE,
        content=body.content,
    )
    await db.commit()
    await db.refresh(entry)
    return entry
