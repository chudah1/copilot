from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.ai_monitor import classify_event
from app.services.market_data import fetch_company_data
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.conviction_log import EVIDENCE_RECEIVED, append_log_entry
from app.services.noise_filter import (
    EVIDENCE_TYPE_MAP,
    apply_priority_suppression,
    filter_candidates,
    record_signal_fired,
)
from app.services.signal_matching import (
    build_evidence_summary,
    determine_verdict,
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
    status: str  # completed | rate_limited
    events_created: int = 0
    next_available_at: datetime | None = None
    created_event_ids: list[uuid.UUID] = field(default_factory=list)
    snapshot: MarketSnapshot | None = None


def _build_snapshot(
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

    # P&L vs cost basis
    cost_basis = float(holding.average_cost_basis)
    snapshot.cost_basis = cost_basis
    if company_data.current_price is not None and cost_basis > 0:
        total_cost = float(holding.quantity) * cost_basis
        total_value = float(holding.quantity) * company_data.current_price
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
    company_data = await fetch_company_data(holding.ticker)

    # Generate monitoring candidates
    previous_price = float(holding.current_price) if holding.current_price is not None else None
    candidates = generate_monitoring_candidates(
        thesis.interpretation,
        company_data,
        previous_price,
        now=now,
    )

    # Signal linking: load decomposition and enrich candidates
    decomposition = await load_active_decomposition(db, thesis.id)
    claims = decomposition.claims if decomposition else None
    candidates = match_candidates_to_signals(candidates, claims)

    # Build lookup tables for narrative generation
    claims_by_id: dict[str, Any] = {}
    signals_by_id: dict[str, Any] = {}
    if claims:
        for claim in claims:
            claims_by_id[str(claim.id)] = claim
            for entity in claim.entities:
                for signal in entity.signals:
                    signals_by_id[str(signal.id)] = signal

    # Build snapshot — always returned, even when 0 events
    snapshot = _build_snapshot(company_data, holding, previous_price, thesis)

    # Update holding price
    if company_data and company_data.current_price is not None:
        holding.current_price = company_data.current_price
        holding.current_value = float(holding.quantity) * company_data.current_price

    # Noise suppression: filter before classification (rules 1, 2, 4)
    candidates = await filter_candidates(candidates, holding.id, signals_by_id, db, now=now)

    # Classify all surviving candidates
    classified: list[tuple[dict[str, Any], str, str | None]] = []  # (candidate, severity, ai_analysis)
    for candidate in candidates:
        classification = await classify_event(
            why_own_it=thesis.why_own_it,
            must_remain_true=thesis.must_remain_true,
            what_would_change_my_mind=thesis.what_would_change_my_mind,
            ai_summary=thesis.ai_summary,
            event_description=candidate["description"],
        )
        severity = classification.severity if classification else "warning"
        ai_analysis = classification.analysis if classification else None
        classified.append((candidate, severity, ai_analysis))

    # Rule 3: Priority suppression (post-classification)
    suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
    surviving_set = {id(c) for c, _ in suppressed}
    classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]

    created_event_ids: list[uuid.UUID] = []

    for candidate, severity, ai_analysis in classified:
        evidence = candidate.get("evidence", {})
        source_url = evidence.get("url")

        # Extract signal linking from enriched evidence
        evidence_signal_id = evidence.get("signal_id")
        evidence_claim_id = evidence.get("claim_id")
        claim_obj = claims_by_id.get(evidence_claim_id) if evidence_claim_id else None
        signal_obj = signals_by_id.get(evidence_signal_id) if evidence_signal_id else None

        evidence_summary = build_evidence_summary(
            candidate=candidate,
            claim_text=claim_obj.claim_text if claim_obj else None,
            signal_label=signal_obj.signal_label if signal_obj else None,
            why_own_it=thesis.why_own_it,
        )
        verdict = determine_verdict(severity)
        evidence_type = EVIDENCE_TYPE_MAP.get(candidate["event_type"], candidate["event_type"])

        event = MonitoringEvent(
            holding_id=holding.id,
            thesis_id=thesis.id,
            event_type=candidate["event_type"],
            severity=severity,
            title=f"Review {holding.ticker}",
            summary=candidate["description"],
            source_url=source_url,
            ai_analysis=ai_analysis,
            raw_data={
                "provider": settings.market_data_provider,
                "candidate_type": candidate["event_type"],
                "evidence": evidence,
            },
            claim_id=uuid.UUID(evidence_claim_id) if evidence_claim_id else None,
            signal_id=uuid.UUID(evidence_signal_id) if evidence_signal_id else None,
            evidence_type=evidence_type,
            evidence_summary=evidence_summary,
            verdict=verdict,
        )
        db.add(event)
        created_event_ids.append(event.id)
        await record_signal_fired(evidence_signal_id, signals_by_id, now=now)
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=thesis.user_id,
            entry_type=EVIDENCE_RECEIVED,
            content=evidence_summary or candidate["description"][:300],
            metadata={"event_type": candidate["event_type"], "severity": severity},
            claim_id=uuid.UUID(evidence_claim_id) if evidence_claim_id else None,
            signal_id=uuid.UUID(evidence_signal_id) if evidence_signal_id else None,
        )

        if severity == "thesis_breaking" and thesis.status in ("active", "draft"):
            thesis.status = "needs_review"

    await db.commit()

    return CheckNowResult(
        status="completed",
        events_created=len(created_event_ids),
        created_event_ids=created_event_ids,
        snapshot=snapshot,
    )
