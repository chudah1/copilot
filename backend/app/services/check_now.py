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
from app.services.ai_monitor import classify_event
from app.services.market_data import fetch_company_data
from app.services.monitoring import generate_monitoring_candidates

logger = logging.getLogger(__name__)

RATE_LIMIT_HOURS = 4


@dataclass
class CheckNowResult:
    status: str  # completed | rate_limited
    events_created: int = 0
    next_available_at: datetime | None = None
    created_event_ids: list[uuid.UUID] = field(default_factory=list)


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
    candidates = generate_monitoring_candidates(
        thesis.interpretation,
        company_data,
        float(holding.current_price) if holding.current_price is not None else None,
        now=now,
    )

    # Update holding price
    if company_data and company_data.current_price is not None:
        holding.current_price = company_data.current_price
        holding.current_value = float(holding.quantity) * company_data.current_price

    created_event_ids: list[uuid.UUID] = []

    seen_candidate_ids: set[str] = set()
    for candidate in candidates:
        evidence = candidate.get("evidence", {})
        dedupe_id = (
            evidence.get("article_id")
            or evidence.get("transaction_id")
            or evidence.get("transcript_id")
        )
        if dedupe_id:
            if dedupe_id in seen_candidate_ids:
                continue
            seen_candidate_ids.add(dedupe_id)

        classification = await classify_event(
            why_own_it=thesis.why_own_it,
            must_remain_true=thesis.must_remain_true,
            what_would_change_my_mind=thesis.what_would_change_my_mind,
            ai_summary=thesis.ai_summary,
            event_description=candidate["description"],
        )

        severity = classification.severity if classification else "warning"
        ai_analysis = classification.analysis if classification else None
        source_url = evidence.get("url")

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
        )
        db.add(event)
        created_event_ids.append(event.id)

        if severity == "thesis_breaking" and thesis.status in ("active", "draft"):
            thesis.status = "needs_review"

    await db.commit()

    return CheckNowResult(
        status="completed",
        events_created=len(created_event_ids),
        created_event_ids=created_event_ids,
    )
