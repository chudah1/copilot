"""What-If Trade Simulator — stateless, no persistence."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.market_data import fetch_company_data


@dataclass
class PortfolioSnapshot:
    total_value: float
    total_cost: float
    holdings_count: int
    top_3_concentration_pct: float
    sector_breakdown: dict[str, float]


@dataclass
class SimulationWarning:
    warning_type: str  # concentration | sector_concentration | missing_thesis | overlap
    message: str


@dataclass
class SimulationResult:
    ticker: str
    name: str
    simulated_quantity: float
    simulated_price: float
    simulated_value: float
    before: PortfolioSnapshot
    after: PortfolioSnapshot
    warnings: list[SimulationWarning] = field(default_factory=list)


def _holding_cost(holding: Holding) -> float:
    return float(holding.quantity) * float(holding.average_cost_basis)


def _holding_value(holding: Holding) -> float:
    return float(holding.current_value) if holding.current_value is not None else _holding_cost(holding)


def _compute_snapshot(
    holdings: list[Holding],
) -> PortfolioSnapshot:
    total_value = 0.0
    total_cost = 0.0
    sector_totals: dict[str, float] = {}

    for h in holdings:
        cost = _holding_cost(h)
        value = _holding_value(h)
        total_value += value
        total_cost += cost
        sector = h.sector or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value

    sorted_values = sorted(
        (_holding_value(h) for h in holdings),
        reverse=True,
    )
    top_3_value = sum(sorted_values[:3])
    top_3_pct = round(top_3_value / total_value * 100, 2) if total_value > 0 else 0.0

    grand = sum(sector_totals.values())
    sector_breakdown = {k: round(v / grand * 100, 2) for k, v in sector_totals.items()} if grand > 0 else {}

    return PortfolioSnapshot(
        total_value=total_value,
        total_cost=total_cost,
        holdings_count=len(holdings),
        top_3_concentration_pct=top_3_pct,
        sector_breakdown=sector_breakdown,
    )


async def simulate_trade(
    user_id: uuid.UUID,
    ticker: str,
    quantity: float,
    price_per_share: float,
    db: AsyncSession,
) -> SimulationResult:
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )
    holdings = list(holdings_result.scalars().all())

    before = _compute_snapshot(holdings)

    # Try to get sector for the simulated ticker
    sim_sector: str | None = None
    sim_name = ticker
    existing = next((h for h in holdings if h.ticker.upper() == ticker.upper()), None)
    if existing:
        sim_sector = existing.sector
        sim_name = existing.name

    if sim_sector is None:
        try:
            company_data = await fetch_company_data(ticker)
            sim_sector = company_data.sector or None
            sim_name = company_data.name or ticker
        except Exception:
            pass

    sim_value = quantity * price_per_share

    # Build virtual holdings list with the simulated trade added
    virtual_holdings: list[Holding] = []
    merged = False
    for h in holdings:
        if h.ticker.upper() == ticker.upper():
            clone = Holding(
                id=h.id, user_id=h.user_id, ticker=h.ticker, name=h.name,
                quantity=float(h.quantity) + quantity,
                average_cost_basis=h.average_cost_basis,
                current_price=price_per_share,
                current_value=_holding_value(h) + sim_value,
                sector=h.sector, geography=h.geography, currency=h.currency,
            )
            virtual_holdings.append(clone)
            merged = True
        else:
            virtual_holdings.append(h)

    if not merged:
        virtual_holdings.append(
            Holding(
                id=uuid.uuid4(), user_id=user_id, ticker=ticker.upper(), name=sim_name,
                quantity=quantity, average_cost_basis=price_per_share,
                current_price=price_per_share, current_value=sim_value,
                sector=sim_sector, currency="GBP",
            )
        )

    after = _compute_snapshot(virtual_holdings)

    # Check for thesis on the simulated ticker
    has_thesis = False
    if existing:
        thesis_result = await db.execute(
            select(Thesis).where(
                Thesis.holding_id == existing.id,
                Thesis.user_id == user_id,
                Thesis.status.in_(["draft", "active", "needs_review"]),
            )
        )
        has_thesis = thesis_result.scalar_one_or_none() is not None

    # Generate warnings
    warnings: list[SimulationWarning] = []

    # Single holding > 20% of after portfolio
    sim_after_value = sim_value + (_holding_value(existing) if existing is not None else 0)
    if after.total_value > 0 and (sim_after_value / after.total_value * 100) > 20:
        pct = round(sim_after_value / after.total_value * 100, 1)
        warnings.append(SimulationWarning(
            warning_type="concentration",
            message=f"{ticker.upper()} would be {pct}% of your portfolio — high single-stock concentration.",
        ))

    # Sector > 40%
    sim_sector_label = sim_sector or "Unknown"
    sector_pct = after.sector_breakdown.get(sim_sector_label, 0)
    if sector_pct > 40:
        warnings.append(SimulationWarning(
            warning_type="sector_concentration",
            message=f"{sim_sector_label} sector would be {sector_pct}% of your portfolio.",
        ))

    if not has_thesis and not existing:
        warnings.append(SimulationWarning(
            warning_type="missing_thesis",
            message=f"You don't have a thesis for {ticker.upper()} yet. Write one before buying.",
        ))
    elif existing and not has_thesis:
        warnings.append(SimulationWarning(
            warning_type="missing_thesis",
            message=f"You already hold {ticker.upper()} but don't have an active thesis. Consider writing one.",
        ))

    return SimulationResult(
        ticker=ticker.upper(),
        name=sim_name,
        simulated_quantity=quantity,
        simulated_price=price_per_share,
        simulated_value=sim_value,
        before=before,
        after=after,
        warnings=warnings,
    )
