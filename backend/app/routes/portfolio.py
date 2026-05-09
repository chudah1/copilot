import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.broker_connection import ConnectBrokerRequest, BrokerConnectionResponse
from app.schemas.holding import HoldingResponse, ManualHoldingRequest, PortfolioSummary
from app.services.encryption import encrypt, decrypt
from app.services.trading212 import Trading212Client

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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
    holdings_with_theses = set()
    theses_active = 0
    theses_need_review = 0

    for h in holdings:
        cost = float(h.quantity) * float(h.average_cost_basis)
        value = float(h.current_value) if h.current_value is not None else cost
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
        )
        theses = theses_result.scalars().all()

        for thesis in theses:
            holdings_with_theses.add(thesis.holding_id)
            if thesis.status == "active":
                theses_active += 1
            elif thesis.status == "needs_review":
                theses_need_review += 1

    theses_missing = len(holdings) - len(holdings_with_theses)

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    def to_pct(totals: dict[str, float]) -> dict[str, float]:
        grand = sum(totals.values())
        if grand == 0:
            return {k: 0.0 for k in totals}
        return {k: round(v / grand * 100, 2) for k, v in totals.items()}

    return PortfolioSummary(
        total_value=total_value,
        total_cost=total_cost,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        holdings_count=len(holdings),
        theses_active=theses_active,
        theses_need_review=theses_need_review,
        theses_missing=theses_missing,
        sector_breakdown=to_pct(sector_totals),
        geography_breakdown=to_pct(geography_totals),
    )
