import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.edgar import build_edgar_candidates, get_recent_8k_filings
from app.services.monitoring_gap_writer import write_monitoring_gap
from app.services.monitoring_pipeline import (
    build_claim_signal_lookup,
    classify_candidates_for_thesis,
    extract_news_watches,
    load_investor_profile,
    match_thesis_news_watches,
    persist_classified_candidates,
)
from app.services.noise_filter import apply_priority_suppression, apply_thesis_floor, filter_candidates
from app.services.signal_matching import load_active_decomposition, match_candidates_to_signals

logger = logging.getLogger(__name__)

# Only material events that warrant immediate surfacing — exec changes and guidance wait for the daily run
HIGH_MATERIALITY_ITEMS = frozenset({"1.02", "1.03", "2.01", "2.02", "2.05", "2.06", "4.02"})

_LOOKBACK_DAYS = 1  # EDGAR API is date-granular; dedup (edgar_accession) prevents re-firing within the day


async def run_edgar_watch():
    run_id = str(uuid.uuid4())
    since = (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).date()
    logger.info("Starting edgar_watch run_id=%s since=%s", run_id, since)

    async with async_session() as db:
        result = await db.execute(
            select(Thesis, Holding)
            .join(Holding, Thesis.holding_id == Holding.id)
            .options(selectinload(Thesis.user))
            .where(Thesis.status == "active")
        )
        rows = result.all()

        for thesis, holding in rows:
            try:
                filings = await get_recent_8k_filings(holding.ticker, since=since)
            except Exception as exc:
                logger.warning("edgar_watch EDGAR failure for %s: %s", holding.ticker, exc)
                await write_monitoring_gap(db, thesis.id, "edgar", str(exc), run_id)
                await db.commit()
                continue

            # Filter to high-materiality items only
            high_mat_filings = [
                f for f in filings
                if any(item in HIGH_MATERIALITY_ITEMS for item in f.items)
            ]
            if not high_mat_filings:
                continue

            candidates = build_edgar_candidates(holding.ticker, high_mat_filings)
            if not candidates:
                continue

            decomposition = await load_active_decomposition(db, thesis.id)
            claims = decomposition.claims if decomposition else None
            candidates = match_candidates_to_signals(candidates, claims)

            # News-watch matching — must run before noise filtering
            news_watches = extract_news_watches(claims)
            nw_matched = await match_thesis_news_watches(candidates, news_watches)

            candidates = apply_thesis_floor(candidates, thesis.created_at)

            # build_claim_signal_lookup returns (claims_by_id, signals_by_id)
            claims_by_id, signals_by_id = build_claim_signal_lookup(claims)

            candidates = await filter_candidates(candidates, holding.id, signals_by_id, db)

            if not candidates:
                continue

            investor_profile = await load_investor_profile(db, thesis.user_id)
            classified = await classify_candidates_for_thesis(
                thesis,
                candidates,
                investor_profile=investor_profile,
                sector=holding.sector,
                ticker=holding.ticker,
                company_name=holding.name,
                nw_matched=nw_matched,
            )

            # apply_priority_suppression takes list of (candidate, severity) tuples
            suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
            surviving_set = {id(c) for c, _ in suppressed}
            classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]

            if classified:
                now = datetime.now(timezone.utc)
                await persist_classified_candidates(
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
                logger.info(
                    "edgar_watch: persisted %d events for thesis %s", len(classified), thesis.id
                )

    logger.info("edgar_watch complete run_id=%s", run_id)
