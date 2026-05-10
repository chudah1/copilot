import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.monitoring_event import MonitoringEvent
from app.services.monitoring import check_thesis_metrics, check_price_move
from app.services.market_data import fetch_company_data
from app.services.ai_monitor import classify_event

logger = logging.getLogger(__name__)

MAX_MONITORED_POSITIONS = 50


async def run_monitoring():
    logger.info("Starting daily monitoring run")

    async with async_session() as db:
        result = await db.execute(
            select(Thesis)
            .where(Thesis.status.in_(["active", "needs_review"]))
            .limit(MAX_MONITORED_POSITIONS)
        )
        active_theses = result.scalars().all()

        for thesis in active_theses:
            try:
                holding_result = await db.execute(
                    select(Holding).where(Holding.id == thesis.holding_id)
                )
                holding = holding_result.scalar_one_or_none()
                if holding is None:
                    continue

                company_data = await fetch_company_data(holding.ticker)

                triggers = []

                if company_data:
                    market_values = {
                        "revenue_growth_yoy": company_data.revenue_growth_yoy,
                        "earnings_growth_yoy": company_data.earnings_growth_yoy,
                        "pe_ratio": company_data.pe_ratio,
                        "dividend_yield": company_data.dividend_yield,
                    }
                    market_values = {k: v for k, v in market_values.items() if v is not None}
                    breaches = check_thesis_metrics(thesis.key_metrics, market_values)
                    for b in breaches:
                        if b.breached:
                            triggers.append(
                                f"Metric breach: {b.metric} is {b.actual_value} "
                                f"(thesis requires {b.operator} {b.threshold})"
                            )

                if not triggers:
                    continue

                event_description = "; ".join(triggers)
                classification = await classify_event(
                    bull_case=thesis.bull_case,
                    key_metrics=thesis.key_metrics,
                    risk_factors=thesis.risk_factors,
                    event_description=event_description,
                )

                severity = classification.severity if classification else "warning"
                ai_analysis = classification.analysis if classification else None

                event = MonitoringEvent(
                    holding_id=holding.id,
                    thesis_id=thesis.id,
                    event_type="metric_breach",
                    severity=severity,
                    title=f"Metric alert for {holding.ticker}",
                    summary=event_description,
                    ai_analysis=ai_analysis,
                )
                db.add(event)

                if severity == "thesis_breaking" and thesis.status == "active":
                    thesis.status = "needs_review"

            except Exception as e:
                logger.error(f"Monitoring failed for thesis {thesis.id}: {e}")
                continue

        await db.commit()

    logger.info("Daily monitoring run complete")
