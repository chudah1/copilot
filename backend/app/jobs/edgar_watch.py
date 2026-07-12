import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.edgar import build_edgar_candidates, get_recent_8k_filings
from app.services.evidence_chunking import best_effort_persist_candidate_evidence_chunks
from app.services.coverage import (
    STAGE_AFTER_CLASSIFICATION,
    STAGE_AFTER_EMBEDDING_ENRICH,
    STAGE_AFTER_LLM_ADJUDICATION,
    STAGE_AFTER_MATCH,
    STAGE_AFTER_NOISE_FILTER,
    STAGE_AFTER_RELEVANCE_FILTER,
    STAGE_AFTER_SAME_EVENT_MERGE,
    STAGE_AFTER_THESIS_FLOOR,
    STAGE_CANDIDATES_GENERATED,
    STAGE_EVENTS_PERSISTED,
    CoveragePassBuilder,
)
from app.services.monitoring_gap_writer import write_monitoring_gap
from app.services.monitoring_pipeline import (
    build_claim_signal_lookup,
    classify_candidates_for_thesis,
    expand_transcript_candidates_for_signals,
    extract_news_watches,
    load_investor_profile,
    match_thesis_news_watches,
    persist_classified_candidates,
    signal_search_descriptors_from_claims,
)
from app.services.noise_filter import apply_priority_suppression, apply_thesis_floor, filter_candidates
from app.services.signal_matching import (
    adjudicate_signal_matches,
    enrich_candidates_with_embedding_matches,
    load_active_decomposition,
    match_candidates_to_signals,
)
from app.services.thesis_relevance_filter import filter_candidates_by_thesis_relevance

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
            coverage = CoveragePassBuilder(
                thesis_id=thesis.id,
                holding_id=holding.id,
                run_id=run_id,
                triggered_by="edgar_watch",
            )
            try:
                filings = await get_recent_8k_filings(holding.ticker, since=since)
            except Exception as exc:
                logger.warning("edgar_watch EDGAR failure for %s: %s", holding.ticker, exc)
                await write_monitoring_gap(db, thesis.id, "edgar", str(exc), run_id)
                coverage.record_source("edgar_8k", candidates_returned=0, error=str(exc))
                coverage.record_stage(STAGE_CANDIDATES_GENERATED, 0)
                coverage.record_stage(STAGE_AFTER_NOISE_FILTER, 0)
                coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
                coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, 0)
                coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
                coverage.record_events_persisted(0)
                await coverage.persist(db)
                await db.commit()
                continue

            # Filter to high-materiality items only
            high_mat_filings = [
                f for f in filings
                if any(item in HIGH_MATERIALITY_ITEMS for item in f.items)
            ]
            coverage.record_source("edgar_8k", candidates_returned=len(high_mat_filings))
            if not high_mat_filings:
                coverage.record_stage(STAGE_CANDIDATES_GENERATED, 0)
                coverage.record_stage(STAGE_AFTER_NOISE_FILTER, 0)
                coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
                coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, 0)
                coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
                coverage.record_events_persisted(0)
                await coverage.persist(db)
                await db.commit()
                continue

            candidates = build_edgar_candidates(holding.ticker, high_mat_filings)
            if not candidates:
                coverage.record_stage(STAGE_CANDIDATES_GENERATED, 0)
                coverage.record_stage(STAGE_AFTER_NOISE_FILTER, 0)
                coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
                coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, 0)
                coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
                coverage.record_events_persisted(0)
                await coverage.persist(db)
                await db.commit()
                continue

            decomposition = await load_active_decomposition(db, thesis.id)
            claims = decomposition.claims if decomposition else None
            signal_descriptors = signal_search_descriptors_from_claims(claims)
            coverage.record_stage(STAGE_CANDIDATES_GENERATED, len(candidates))
            candidates = match_candidates_to_signals(candidates, claims)
            coverage.record_stage(STAGE_AFTER_MATCH, len(candidates))
            candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
            coverage.record_stage(STAGE_AFTER_EMBEDDING_ENRICH, len(candidates))
            candidates = await adjudicate_signal_matches(candidates, claims)
            coverage.record_stage(STAGE_AFTER_LLM_ADJUDICATION, len(candidates))
            if claims:
                candidates = await filter_candidates_by_thesis_relevance(
                    candidates,
                    signal_descriptors=signal_descriptors,
                    ticker=holding.ticker,
                    why_own_it=thesis.why_own_it or "",
                )
                coverage.record_stage(STAGE_AFTER_RELEVANCE_FILTER, len(candidates))
                candidates = match_candidates_to_signals(candidates, claims)
                candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
                candidates = await adjudicate_signal_matches(candidates, claims)

            # News-watch matching — must run before noise filtering
            news_watches = extract_news_watches(claims)
            nw_matched = await match_thesis_news_watches(candidates, news_watches)
            candidates = await expand_transcript_candidates_for_signals(candidates, claims)
            await best_effort_persist_candidate_evidence_chunks(
                db, thesis=thesis, holding=holding, candidates=candidates
            )

            candidates = apply_thesis_floor(candidates, thesis.created_at)
            coverage.record_stage(STAGE_AFTER_THESIS_FLOOR, len(candidates))

            # build_claim_signal_lookup returns (claims_by_id, signals_by_id)
            claims_by_id, signals_by_id = build_claim_signal_lookup(claims)

            candidates = await filter_candidates(candidates, holding.id, signals_by_id, db)
            coverage.record_stage(STAGE_AFTER_NOISE_FILTER, len(candidates))

            if not candidates:
                coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
                coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, 0)
                coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
                coverage.record_events_persisted(0)
                await coverage.persist(db)
                await db.commit()
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
            coverage.record_stage(STAGE_AFTER_CLASSIFICATION, len(classified))
            suppression = await apply_priority_suppression(
                [(c, s) for c, s, _ in classified],
                holding_id=holding.id,
            )
            coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, suppression.after_same_event_merge_count)
            surviving_set = {id(c) for c, _ in suppression.classified}
            classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]

            created_event_ids: list[uuid.UUID] = []
            if classified:
                now = datetime.now(timezone.utc)
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
            coverage.record_stage(STAGE_EVENTS_PERSISTED, len(created_event_ids))
            coverage.record_events_persisted(len(created_event_ids))
            await coverage.persist(db)
            await db.commit()
            if classified:
                logger.info(
                    "edgar_watch: persisted %d events for thesis %s", len(created_event_ids), thesis.id
                )

    logger.info("edgar_watch complete run_id=%s", run_id)
