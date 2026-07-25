import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.monitoring_event import MonitoringEvent
from app.services.check_now import HoldingSnapshot, ThesisSnapshot
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.thesis_health import maybe_notify_band_drop, refresh_thesis_health
from app.services.market_data import (
    MAX_CURRENT_TRANSCRIPT_AGE_DAYS,
    CompanyData,
    fetch_company_data,
    shortlist_qualitative_candidates,
    transcript_fetch_diagnostics,
)
from app.services.valuation import apply_market_price
from app.services.noise_filter import (
    apply_priority_suppression,
    apply_thesis_floor,
    filter_candidates,
)
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
from app.services.edgar import (
    build_edgar_candidates,
    build_form4_candidates,
    get_recent_8k_filings,
    get_recent_form4_transactions,
)
from app.services.edgar_extractor import enrich_earnings_candidates
from app.services.evidence_chunking import best_effort_persist_candidate_evidence_chunks
from app.services.news_collector import collect_news_evidence
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
from app.services.signal_matching import (
    load_active_decomposition,
    adjudicate_signal_matches,
    enrich_candidates_with_embedding_matches,
    match_candidates_to_signals,
)
from app.services.monitoring_gap_writer import write_monitoring_gap
from app.services.thesis_relevance_filter import (
    apply_drop_thesis_floor,
    filter_candidates_by_thesis_relevance_with_drops,
)

logger = logging.getLogger(__name__)


def _requires_market_data_key() -> bool:
    return settings.market_data_provider == "alpha_vantage"


def _extract_proxy_tickers(interpretation: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract proxy_signals from a thesis interpretation."""
    if not interpretation:
        return []
    signals = interpretation.get("proxy_signals", [])
    if not isinstance(signals, list):
        return []
    return [s for s in signals if isinstance(s, dict) and s.get("ticker")]


def _proxy_interpretation_for_metrics(
    interpretation: dict[str, Any] | None,
    proxy_signal: dict[str, Any],
) -> dict[str, Any] | None:
    if not interpretation:
        return None

    watch_hints = interpretation.get("watch_hints", [])
    if not isinstance(watch_hints, list):
        return None

    allowed_metrics = proxy_signal.get("allowed_metrics", [])
    if not isinstance(allowed_metrics, list) or not allowed_metrics:
        return None
    allowed_metric_set = {str(metric).strip() for metric in allowed_metrics if str(metric).strip()}

    filtered_hints: list[dict[str, Any]] = []
    for hint in watch_hints:
        if not isinstance(hint, dict):
            continue
        if hint.get("kind") != "metric_threshold":
            continue
        if hint.get("metric") not in allowed_metric_set:
            continue
        filtered_hints.append(hint)

    if not filtered_hints:
        return None
    return {"watch_hints": filtered_hints}


def _generate_proxy_candidates(
    proxy_data: CompanyData,
    proxy_signal: dict[str, Any],
    interpretation: dict[str, Any] | None,
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Generate monitoring candidates from a proxy ticker's qualitative signals.

    Qualitative signals are always checked. Metric thresholds are checked only
    when the proxy explicitly declares those metrics as relevant, so we avoid
    blindly reusing parent-company thresholds across unrelated entities.
    """
    proxy_rationale = str(proxy_signal.get("rationale", "")).strip()
    proxy_signal_hint = str(proxy_signal.get("signal_hint", "")).strip()
    candidates = shortlist_qualitative_candidates(
        proxy_data.news_items,
        proxy_data.recent_earnings_surprise_pct,
        proxy_data.upcoming_earnings_date,
        getattr(proxy_data, "earnings_call", None),
        getattr(proxy_data, "earnings_calls", []),
        getattr(proxy_data, "insider_transactions", []),
        now=now,
        ticker=proxy_data.ticker,
    )

    proxy_market_values = {
        "revenue_growth_yoy": proxy_data.revenue_growth_yoy,
        "earnings_growth_yoy": proxy_data.earnings_growth_yoy,
        "pe_ratio": proxy_data.pe_ratio,
        "dividend_yield": proxy_data.dividend_yield,
    }
    proxy_market_values = {k: v for k, v in proxy_market_values.items() if v is not None}
    proxy_metric_interpretation = _proxy_interpretation_for_metrics(interpretation, proxy_signal)
    if proxy_metric_interpretation and proxy_market_values:
        for breach in check_metric_watch_hints(proxy_metric_interpretation, proxy_market_values):
            if breach.breached:
                candidates.append(
                    {
                        "event_type": "metric_threshold",
                        "description": (
                            f"Proxy metric breached: {proxy_data.ticker} {breach.metric} is "
                            f"{breach.actual_value} (expected {breach.operator} {breach.threshold})."
                        ),
                        "evidence": {
                            "metric": breach.metric,
                            "actual_value": breach.actual_value,
                            "operator": breach.operator,
                            "threshold": breach.threshold,
                            "rationale": breach.rationale,
                        },
                    }
                )

    # Tag each candidate as coming from a proxy ticker
    for candidate in candidates:
        candidate["description"] = (
            f"[Proxy: {proxy_data.ticker}] {candidate['description']}"
        )
        candidate["evidence"]["proxy_ticker"] = proxy_data.ticker
        candidate["evidence"]["proxy_rationale"] = proxy_rationale
        if proxy_signal_hint:
            candidate["evidence"]["proxy_signal_hint"] = proxy_signal_hint
    return candidates


async def _maybe_create_monitoring_inactive_event(
    db,
    active_theses: list[Thesis],
) -> bool:
    if not _requires_market_data_key() or settings.alpha_vantage_api_key or not active_theses:
        return False

    existing = await db.execute(
        select(MonitoringEvent)
        .where(MonitoringEvent.event_type == "monitoring_inactive")
        .where(MonitoringEvent.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
        .limit(1)
    )
    if existing.scalar_one_or_none() is None:
        first_thesis = active_theses[0]
        holding_result = await db.execute(select(Holding).where(Holding.id == first_thesis.holding_id))
        holding = holding_result.scalar_one_or_none()
        if holding is not None:
            db.add(
                MonitoringEvent(
                    holding_id=holding.id,
                    thesis_id=first_thesis.id,
                    event_type="monitoring_inactive",
                    severity="info",
                    title="Monitoring is not active",
                    summary="No Alpha Vantage API key is configured. Set ALPHA_VANTAGE_API_KEY in your .env to enable market data monitoring.",
                    ai_analysis=None,
                    raw_data={"reason": "missing_alpha_vantage_api_key"},
                )
            )
            await db.commit()
    logger.warning("No Alpha Vantage API key configured — monitoring skipped")
    return True


async def _load_thesis_holdings_and_tickers(
    db,
    active_theses: list[Thesis],
) -> tuple[dict[str, Holding], set[str]]:
    thesis_holdings: dict[str, Holding] = {}
    all_tickers: set[str] = set()

    for thesis in active_theses:
        holding_result = await db.execute(select(Holding).where(Holding.id == thesis.holding_id))
        holding = holding_result.scalar_one_or_none()
        if holding is None:
            continue
        thesis_holdings[str(thesis.id)] = holding
        direct_ticker = holding.ticker.upper()
        all_tickers.add(direct_ticker)

        for proxy in _extract_proxy_tickers(thesis.interpretation):
            proxy_ticker = proxy["ticker"].upper()
            if proxy_ticker != direct_ticker:
                all_tickers.add(proxy_ticker)

    return thesis_holdings, all_tickers


async def _fetch_ticker_data(tickers: set[str]) -> dict[str, CompanyData | None]:
    ticker_data: dict[str, CompanyData | None] = {}
    for ticker in tickers:
        try:
            ticker_data[ticker] = await fetch_company_data(ticker)
        except Exception as exc:
            logger.error("Failed to fetch data for %s: %s", ticker, exc)
            ticker_data[ticker] = None
    return ticker_data



@dataclass(frozen=True)
class UserSnapshot:
    """Just what the alert helpers need — email + preferences. Snapshotted
    up front so the per-thesis pipeline can send emails without holding the
    DB session across LLM latency."""
    id: uuid.UUID
    email: str | None
    preferences: dict | None


@dataclass(frozen=True)
class MonitoringContext:
    thesis: ThesisSnapshot
    holding: HoldingSnapshot
    user: UserSnapshot


def _session_factory(bind) -> async_sessionmaker:
    return async_sessionmaker(bind, class_=AsyncSession, expire_on_commit=False)


def _snapshot_holding(holding: Holding) -> HoldingSnapshot:
    return HoldingSnapshot(
        id=holding.id,
        user_id=holding.user_id,
        ticker=holding.ticker,
        name=holding.name,
        sector=holding.sector,
        quantity=float(holding.quantity),
        average_cost_basis=float(holding.average_cost_basis),
        current_price=float(holding.current_price) if holding.current_price is not None else None,
        current_value=float(holding.current_value) if holding.current_value is not None else None,
        currency=holding.currency,
    )


def _snapshot_thesis(thesis: Thesis) -> ThesisSnapshot:
    return ThesisSnapshot(
        id=thesis.id,
        user_id=thesis.user_id,
        created_at=thesis.created_at,
        interpretation=thesis.interpretation,
        why_own_it=thesis.why_own_it,
        must_remain_true=thesis.must_remain_true,
        what_would_change_my_mind=thesis.what_would_change_my_mind,
        ai_summary=thesis.ai_summary,
    )


def _snapshot_user(user) -> UserSnapshot:
    return UserSnapshot(
        id=user.id,
        email=getattr(user, "email", None),
        preferences=getattr(user, "preferences", None),
    )


async def _process_monitoring_thesis(
    *,
    ctx: MonitoringContext,
    company_data: CompanyData,
    ticker_data: dict[str, CompanyData | None],
    session_factory: async_sessionmaker,
    run_id: str,
    now: datetime,
) -> None:
    """Per-thesis daily monitoring pass, mirroring run_check_now's three-phase
    session pattern so Neon idle-closes during LLM work can't corrupt the batch."""
    coverage = CoveragePassBuilder(
        thesis_id=ctx.thesis.id,
        holding_id=ctx.holding.id,
        run_id=run_id,
        triggered_by="monitoring_run",
    )

    # Phase 1: prep reads (short session)
    async with session_factory() as prep_db:
        decomposition = await load_active_decomposition(prep_db, ctx.thesis.id)
        claims = decomposition.claims if decomposition else None
        investor_profile = await load_investor_profile(prep_db, ctx.user.id)

    # Direct ticker candidates (external work, no session)
    candidates = generate_monitoring_candidates(
        ctx.thesis.interpretation,
        company_data,
        ctx.holding.current_price,
        now=now,
        transcript_max_age_days=MAX_CURRENT_TRANSCRIPT_AGE_DAYS,
    )
    coverage.record_source("qualitative_market_data", candidates_returned=len(candidates))
    coverage.record_source(
        "earnings_call_transcripts",
        queried=bool(transcript_fetch_diagnostics(company_data).get("requested_quarters")),
        candidates_returned=len(company_data.earnings_calls or []),
        details=transcript_fetch_diagnostics(company_data) or None,
    )

    # Proxy ticker candidates
    proxy_before = len(candidates)
    for proxy in _extract_proxy_tickers(ctx.thesis.interpretation):
        proxy_ticker = proxy["ticker"].upper()
        if proxy_ticker == ctx.holding.ticker:
            continue
        proxy_data = ticker_data.get(proxy_ticker)
        if proxy_data is None:
            continue
        candidates.extend(
            _generate_proxy_candidates(
                proxy_data,
                proxy,
                ctx.thesis.interpretation,
                now=now,
            )
        )
    if len(candidates) > proxy_before:
        coverage.record_source("proxy_tickers", candidates_returned=len(candidates) - proxy_before)

    # EDGAR (external, but the gap-log writes need a session)
    before_edgar = len(candidates)
    try:
        edgar_filings = await get_recent_8k_filings(ctx.holding.ticker)
        candidates.extend(build_edgar_candidates(ctx.holding.ticker, edgar_filings))
        coverage.record_source("edgar_8k", candidates_returned=len(candidates) - before_edgar)
    except Exception as exc:
        logger.warning("EDGAR gap for thesis %s: %s", ctx.thesis.id, exc)
        async with session_factory() as gap_db:
            await write_monitoring_gap(gap_db, ctx.thesis.id, "edgar", str(exc), run_id)
            await gap_db.commit()
        coverage.record_source("edgar_8k", candidates_returned=0, error=str(exc))

    # Form 4
    before_form4 = len(candidates)
    form4_txns = await get_recent_form4_transactions(ctx.holding.ticker)
    candidates.extend(build_form4_candidates(ctx.holding.ticker, form4_txns, now=now))
    coverage.record_source("edgar_form4", candidates_returned=len(candidates) - before_form4)

    # Enrich earnings 8-Ks (LLM, no session)
    candidates = await enrich_earnings_candidates(candidates, ctx.thesis)

    # Gemini
    signal_descriptors = signal_search_descriptors_from_claims(claims)
    before_gemini = len(candidates)
    try:
        gemini_candidates = await collect_news_evidence(
            ctx.holding.ticker,
            ctx.holding.name or ctx.holding.ticker,
            signal_descriptors,
        )
        candidates.extend(gemini_candidates)
        coverage.record_source("gemini_news", candidates_returned=len(candidates) - before_gemini)
    except Exception as exc:
        logger.warning("Gemini gap for thesis %s: %s", ctx.thesis.id, exc)
        async with session_factory() as gap_db:
            await write_monitoring_gap(gap_db, ctx.thesis.id, "gemini_news", str(exc), run_id)
            await gap_db.commit()
        coverage.record_source("gemini_news", candidates_returned=0, error=str(exc))
    coverage.record_stage(STAGE_CANDIDATES_GENERATED, len(candidates))

    # Signal binding + adjudication (LLM, no session)
    candidates = match_candidates_to_signals(candidates, claims)
    coverage.record_stage(STAGE_AFTER_MATCH, len(candidates))
    candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
    coverage.record_stage(STAGE_AFTER_EMBEDDING_ENRICH, len(candidates))
    candidates = await adjudicate_signal_matches(candidates, claims)
    coverage.record_stage(STAGE_AFTER_LLM_ADJUDICATION, len(candidates))
    if claims:
        candidates, reviewed_but_dropped = await filter_candidates_by_thesis_relevance_with_drops(
            candidates,
            signal_descriptors=signal_descriptors,
            ticker=ctx.holding.ticker,
            why_own_it=ctx.thesis.why_own_it or "",
        )
        coverage.record_stage(STAGE_AFTER_RELEVANCE_FILTER, len(candidates))
        coverage.record_reviewed_but_dropped(
            apply_drop_thesis_floor(reviewed_but_dropped, ctx.thesis.created_at, now=now)
        )
        candidates = match_candidates_to_signals(candidates, claims)
        candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
        candidates = await adjudicate_signal_matches(candidates, claims)

    # Thesis-floor drop — strict cutoff at thesis.created_at (unlike check_now
    # which allows a 14-day lookback for first-pulse UX). The daily batch stays
    # strict so we don't resurface already-processed history to established users.
    candidates = apply_thesis_floor(candidates, ctx.thesis.created_at)
    coverage.record_stage(STAGE_AFTER_THESIS_FLOOR, len(candidates))

    nw_matched = await match_thesis_news_watches(candidates, extract_news_watches(claims))
    candidates = await expand_transcript_candidates_for_signals(candidates, claims)

    # Phase 3: chunking + noise filter in a short session
    claims_by_id: dict = {}
    signals_by_id: dict = {}
    if candidates:
        claims_by_id, signals_by_id = build_claim_signal_lookup(claims)
        async with session_factory() as filter_db:
            await best_effort_persist_candidate_evidence_chunks(
                filter_db,
                thesis=ctx.thesis,
                holding=ctx.holding,
                candidates=candidates,
            )
            candidates = await filter_candidates(
                candidates,
                ctx.holding.id,
                signals_by_id,
                filter_db,
                now=now,
            )
        coverage.record_stage(STAGE_AFTER_NOISE_FILTER, len(candidates))
    else:
        coverage.record_stage(STAGE_AFTER_NOISE_FILTER, 0)

    # Classification (LLM, no session)
    classified: list = []
    if candidates:
        classified = await classify_candidates_for_thesis(
            ctx.thesis,
            candidates,
            investor_profile=investor_profile,
            sector=ctx.holding.sector,
            ticker=ctx.holding.ticker,
            company_name=ctx.holding.name,
            nw_matched=nw_matched,
        )
        coverage.record_stage(STAGE_AFTER_CLASSIFICATION, len(classified))
        suppression = await apply_priority_suppression(
            [(c, s) for c, s, _ in classified],
            holding_id=ctx.holding.id,
        )
        coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, suppression.after_same_event_merge_count)
        surviving_set = {id(c) for c, _ in suppression.classified}
        classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]
    else:
        coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
        coverage.record_stage(STAGE_AFTER_SAME_EVENT_MERGE, 0)

    # Phase 4: write session (persist events + apply_market_price + refresh_health + commit)
    pending_alert = None
    score: int | None = None
    new_label: str | None = None
    prev_label: str | None = None
    async with session_factory() as write_db:
        live_holding = (
            await write_db.execute(
                select(Holding).where(
                    Holding.id == ctx.holding.id,
                    Holding.user_id == ctx.holding.user_id,
                )
            )
        ).scalar_one_or_none()
        live_thesis = (
            await write_db.execute(
                select(Thesis).where(
                    Thesis.id == ctx.thesis.id,
                    Thesis.user_id == ctx.thesis.user_id,
                )
            )
        ).scalar_one_or_none()
        if live_holding is None or live_thesis is None:
            logger.warning(
                "thesis/holding vanished mid-run for thesis %s", ctx.thesis.id
            )
            return

        if company_data and company_data.current_price is not None:
            await apply_market_price(
                live_holding,
                native_price=company_data.current_price,
                native_currency=getattr(company_data, "currency", None),
                now=now,
            )
        live_holding.last_monitored_at = now

        status_before = live_thesis.status
        created_event_ids: list = []
        persisted_events: list[MonitoringEvent] = []
        if classified:
            created_event_ids = await persist_classified_candidates(
                write_db,
                thesis=live_thesis,
                holding=live_holding,
                classified=classified,
                claims_by_id=claims_by_id,
                signals_by_id=signals_by_id,
                now=now,
                investor_profile=investor_profile,
                persisted_events_out=persisted_events,
            )
        coverage.record_stage(STAGE_EVENTS_PERSISTED, len(created_event_ids))
        coverage.record_events_persisted(len(created_event_ids))
        try:
            await coverage.persist(write_db)
        except Exception:
            logger.exception(
                "coverage.persist failed inline for thesis %s (events still committing)",
                ctx.thesis.id,
            )

        score, new_label, prev_label = await refresh_thesis_health(
            write_db, live_thesis, claims, decomposition, now=now
        )

        # Select from rows that were actually persisted, then email only after
        # commit so a network hop cannot hold the transaction open.
        from app.services.alerts import prepare_monitoring_alert

        pending_alert = prepare_monitoring_alert(
            email=ctx.user.email,
            preferences=ctx.user.preferences,
            ticker=ctx.holding.ticker,
            status_before=status_before,
            persisted_events=persisted_events,
        )

        await write_db.commit()

    # Phase 5: post-commit emails (no session held)
    alert_sent = False
    if pending_alert:
        from app.services.alerts import send_monitoring_alert

        alert_sent = await send_monitoring_alert(pending_alert)

    preferences = ctx.user.preferences or {}
    if (
        not alert_sent
        and ctx.user.email
        and preferences.get("email_enabled", True) is not False
        and preferences.get("notification_sensitivity", "all") == "all"
        and score is not None
        and new_label is not None
    ):
        await maybe_notify_band_drop(
            user_email=ctx.user.email,
            ticker=ctx.holding.ticker,
            prev_label=prev_label,
            new_label=new_label,
            score=score,
        )


async def run_monitoring():
    import time
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    logger.info("Starting daily monitoring run run_id=%s", run_id)

    # Phase 1: metadata reads in one short session, then snapshot everything.
    # We used to hold this session across the entire batch — 2-3 minutes of LLM
    # work per thesis × N theses — which was the same Neon idle-close exposure
    # we fixed for check_now in 9bdad11.
    contexts: list[MonitoringContext] = []
    all_tickers: set[str] = set()
    session_factory: async_sessionmaker | None = None
    async with async_session() as prep_db:
        session_factory = _session_factory(prep_db.bind)

        result = await prep_db.execute(
            select(Thesis)
            .options(selectinload(Thesis.user))
            .where(Thesis.status.in_(["active", "needs_review"]))
        )
        active_theses = result.scalars().all()

        if await _maybe_create_monitoring_inactive_event(prep_db, active_theses):
            return

        thesis_holdings, all_tickers = await _load_thesis_holdings_and_tickers(prep_db, active_theses)

        for thesis in active_theses:
            holding = thesis_holdings.get(str(thesis.id))
            if holding is None:
                continue
            contexts.append(
                MonitoringContext(
                    thesis=_snapshot_thesis(thesis),
                    holding=_snapshot_holding(holding),
                    user=_snapshot_user(thesis.user) if thesis.user else UserSnapshot(id=thesis.user_id, email=None, preferences=None),
                )
            )

    # Phase 2: fetch all ticker data in parallel/batched (external, no session).
    ticker_data = await _fetch_ticker_data(all_tickers)
    now = datetime.now(timezone.utc)

    # Phase 3: per-thesis pipeline, each with its own short-lived sessions.
    for ctx in contexts:
        company_data = ticker_data.get(ctx.holding.ticker.upper())
        if company_data is None:
            logger.warning(
                "No market data for %s — skipping thesis %s",
                ctx.holding.ticker,
                ctx.thesis.id,
            )
            continue
        try:
            await _process_monitoring_thesis(
                ctx=ctx,
                company_data=company_data,
                ticker_data=ticker_data,
                session_factory=session_factory,
                run_id=run_id,
                now=now,
            )
        except Exception as e:
            logger.error(
                "Monitoring failed for thesis %s: %s",
                ctx.thesis.id,
                e,
                exc_info=True,
            )
            continue

    elapsed = time.monotonic() - started
    logger.info(
        "Daily monitoring run complete — %d theses processed in %.1fs",
        len(contexts),
        elapsed,
    )
