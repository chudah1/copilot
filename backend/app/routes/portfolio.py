import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.dependencies import get_current_user
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.broker_connection import ConnectBrokerRequest, BrokerConnectionResponse
from app.schemas.holding import HoldingResponse, ManualHoldingRequest, PortfolioSummary, PriorityHoldingSummary
from app.services.encryption import encrypt, decrypt
from app.services.trading212 import Trading212Client
from app.services.csv_parser import parse_csv

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _age_in_days(timestamp: datetime) -> int:
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - normalized).days


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


@router.post("/connect", response_model=BrokerConnectionResponse, status_code=status.HTTP_201_CREATED)
async def connect_broker(
    body: ConnectBrokerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.broker_type != "trading212":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only trading212 is supported")

    client = Trading212Client(api_key=body.api_key)
    valid = await client.verify_key()
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API key")

    encrypted_key = encrypt(body.api_key)
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

    api_key = decrypt(connection.encrypted_api_key)
    client = Trading212Client(api_key=api_key)
    positions = await client.fetch_positions()

    synced_holdings = []
    for pos in positions:
        existing_result = await db.execute(
            select(Holding).where(
                Holding.user_id == current_user.id,
                Holding.ticker == pos.ticker,
            )
        )
        holding = existing_result.scalar_one_or_none()

        current_value = pos.quantity * pos.current_price if pos.current_price else None

        if holding is None:
            holding = Holding(
                user_id=current_user.id,
                broker_connection_id=connection.id,
                ticker=pos.ticker,
                name=pos.ticker,
                quantity=pos.quantity,
                average_cost_basis=pos.average_price,
                current_price=pos.current_price,
                current_value=current_value,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)
        else:
            holding.quantity = pos.quantity
            holding.average_cost_basis = pos.average_price
            holding.current_price = pos.current_price
            holding.current_value = current_value
            holding.last_updated_at = datetime.now(timezone.utc)

        synced_holdings.append(holding)

    connection.last_synced_at = datetime.now(timezone.utc)
    await db.commit()

    for h in synced_holdings:
        await db.refresh(h)

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding = Holding(
        user_id=current_user.id,
        ticker=body.ticker,
        name=body.name,
        exchange=body.exchange,
        quantity=body.quantity,
        average_cost_basis=body.average_cost_basis,
        currency=body.currency,
        sector=body.sector,
        geography=body.geography,
        asset_class=body.asset_class,
        last_updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


@router.post("/upload-csv", response_model=list[HoldingResponse], status_code=status.HTTP_201_CREATED)
async def upload_csv(
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
                ticker=p.ticker,
                name=p.name,
                quantity=p.quantity,
                average_cost_basis=p.average_cost_basis,
                currency=p.currency,
                current_value=p.quantity * p.average_cost_basis,
                last_updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)

        created.append(holding)

    await db.commit()
    for h in created:
        await db.refresh(h)

    return created


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
    monitoring_ready = bool(settings.enable_scheduler and settings.alpha_vantage_api_key)
    if not settings.enable_scheduler:
        monitoring_message = "Monitoring is disabled in this environment."
    elif not settings.alpha_vantage_api_key:
        monitoring_message = "Monitoring is not active yet. Add ALPHA_VANTAGE_API_KEY to enable daily portfolio monitoring."
    elif len(holdings_with_current_theses) == 0:
        monitoring_message = "Monitoring is live, but you need at least one current thesis before it can watch anything meaningful."
    else:
        monitoring_message = "Daily monitoring is active. We check your current theses each morning and send a weekly digest on Sunday."

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
        thesis_coverage_pct=round((thesis_coverage_value / total_value * 100), 2) if total_value > 0 else 0.0,
        monitorable_thesis_coverage_pct=round((monitorable_coverage_value / total_value * 100), 2) if total_value > 0 else 0.0,
        stale_theses_count=stale_theses_count,
        unmonitored_holdings_count=unmonitored_holdings_count,
        conviction_mismatch_count=conviction_mismatch_count,
        monitoring_ready=monitoring_ready,
        monitoring_message=monitoring_message,
        sector_breakdown=to_pct(sector_totals),
        geography_breakdown=to_pct(geography_totals),
        attention_queue=attention_queue,
    )
