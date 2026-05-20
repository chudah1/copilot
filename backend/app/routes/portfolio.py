import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.trading212 import Trading212Client, build_auth_header, detect_trading212_base_url
from app.services.csv_parser import parse_csv
from app.services.market_data import detect_native_currency, fetch_company_data, fetch_company_overview, fetch_live_price, get_fx_rate

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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
        return monitoring_ready, "Monitoring is live, but you need at least one current thesis before it can watch anything meaningful."
    return monitoring_ready, "Daily monitoring is active. We check your current theses each morning and send a weekly digest on Sunday."


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

    synced_holdings = []
    for pos in positions:
        existing_result = await db.execute(
            select(Holding).where(
                Holding.user_id == current_user.id,
                Holding.ticker == pos.ticker,
            )
        )
        holding = existing_result.scalar_one_or_none()

        # Determine native currency and convert all monetary values to GBP so
        # portfolio totals are consistent with what T212 shows the user.
        native_currency = detect_native_currency(pos.ticker)
        fx_rate = await get_fx_rate(native_currency, "GBP")
        avg_cost_gbp = pos.average_price * fx_rate
        current_value_gbp = pos.quantity * pos.current_price * fx_rate if pos.current_price else None

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
                pass

            holding = Holding(
                user_id=current_user.id,
                broker_connection_id=connection.id,
                ticker=pos.ticker.upper(),
                name=h_name,
                quantity=pos.quantity,
                average_cost_basis=avg_cost_gbp,
                current_price=pos.current_price,  # native currency per-share (informational)
                current_value=current_value_gbp,   # account currency (GBP)
                currency=native_currency,
                sector=h_sector,
                geography=h_geography,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)
        else:
            holding.quantity = pos.quantity
            holding.average_cost_basis = avg_cost_gbp
            holding.current_price = pos.current_price  # native currency per-share
            holding.current_value = current_value_gbp   # GBP
            holding.currency = native_currency
            holding.last_updated_at = datetime.now(timezone.utc)
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
                    pass

        synced_holdings.append(holding)

    connection.last_synced_at = datetime.now(timezone.utc)
    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()

    for h in synced_holdings:
        await db.refresh(h)

    from app.services.ai_thesis import generate_draft_theses_for_user
    new_holding_ids = [h.id for h in synced_holdings]
    background_tasks.add_task(generate_draft_theses_for_user, current_user.id, new_holding_ids)

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
    # Try to enrich with market data if sector/geography not provided
    enriched_sector = body.sector
    enriched_geography = body.geography
    enriched_name = body.name
    if not enriched_sector or not enriched_geography:
        try:
            overview = await fetch_company_overview(body.ticker)
            if overview:
                if not enriched_sector and overview["sector"] != "Unknown":
                    enriched_sector = overview["sector"]
                if not enriched_geography and overview["country"] != "Unknown":
                    enriched_geography = overview["country"]
                if enriched_name == body.ticker and overview["name"] != body.ticker:
                    enriched_name = overview["name"]
        except Exception:
            pass

    holding = Holding(
        user_id=current_user.id,
        ticker=body.ticker.upper(),
        name=enriched_name,
        exchange=body.exchange,
        quantity=body.quantity,
        average_cost_basis=body.average_cost_basis,
        currency=body.currency,
        sector=enriched_sector,
        geography=enriched_geography,
        asset_class=body.asset_class,
        last_updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.flush()
    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()
    await db.refresh(holding)

    from app.services.ai_thesis import generate_draft_theses_for_user
    background_tasks.add_task(generate_draft_theses_for_user, current_user.id, [holding.id])

    return holding


@router.post("/holdings/enrich", response_model=list[HoldingResponse])
async def enrich_holdings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backfill sector/geography for holdings missing this data."""
    from sqlalchemy import or_

    result = await db.execute(
        select(Holding).where(
            Holding.user_id == current_user.id,
            or_(Holding.sector.is_(None), Holding.geography.is_(None)),
        )
    )
    holdings = result.scalars().all()
    updated = []

    for h in holdings:
        try:
            overview = await fetch_company_overview(h.ticker)
            if not overview:
                continue
            if not h.sector and overview["sector"] != "Unknown":
                h.sector = overview["sector"]
            if not h.geography and overview["country"] != "Unknown":
                h.geography = overview["country"]
            if h.name == h.ticker and overview["name"] != h.ticker:
                h.name = overview["name"]
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

    parsed = parse_csv(text)
    if not parsed:
        raise HTTPException(status_code=400, detail="No holdings found in CSV. Check the format.")

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

        if holding:
            holding.quantity = p.quantity
            holding.average_cost_basis = p.average_cost_basis
            holding.currency = p.currency
            holding.name = p.name
            holding.last_updated_at = datetime.now(timezone.utc)
        else:
            holding = Holding(
                user_id=current_user.id,
                ticker=p.ticker.upper(),
                name=p.name,
                quantity=p.quantity,
                average_cost_basis=p.average_cost_basis,
                currency=p.currency,
                current_value=p.quantity * p.average_cost_basis,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)

        created.append(holding)

    from app.services.onboarding import mark_portfolio_connected
    await mark_portfolio_connected(db, current_user.id)
    await db.commit()
    for h in created:
        await db.refresh(h)

    from app.services.ai_thesis import generate_draft_theses_for_user
    new_ids = [h.id for h in created]
    background_tasks.add_task(generate_draft_theses_for_user, current_user.id, new_ids)

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
        native_ccy = holding.currency or detect_native_currency(holding.ticker)
        fx_rate = await get_fx_rate(native_ccy, "GBP")
        current_value_gbp = float(holding.quantity) * price * fx_rate
        return {
            "ticker": holding.ticker,
            "current_price": price,
            "current_value": round(current_value_gbp, 2),
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
                "reason": p.reason,
                "latest_event_summary": p.latest_event_summary,
                "days_since_thesis_update": p.days_since_thesis_update,
                "has_thesis": p.has_thesis,
                "pnl_pct": p.pnl_pct,
                "last_checked_at": p.last_checked_at,
                "recent_event_count": p.recent_event_count,
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
    return PortfolioTrendResponse(
        snapshot_date=snap.snapshot_date.isoformat(),
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


@router.get("/holdings/{holding_id}/conviction-log", response_model=ConvictionLogResponse)
async def get_conviction_log(
    holding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.conviction_log_entry import ConvictionLogEntry
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

    return ConvictionLogResponse(
        entries=entries,
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
