import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.monitoring_event import MonitoringEvent
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.thesis_health import maybe_notify_band_drop, refresh_thesis_health
from app.services.market_data import CompanyData, fetch_company_data, shortlist_qualitative_candidates
from app.services.valuation import apply_market_price
from app.services.noise_filter import (
    apply_priority_suppression,
    apply_thesis_floor,
    filter_candidates,
)
from app.services.monitoring_pipeline import (
    build_claim_signal_lookup,
    classify_candidates_for_thesis,
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
from app.services.news_collector import collect_news_evidence
from app.services.coverage import (
    STAGE_AFTER_CLASSIFICATION,
    STAGE_AFTER_EMBEDDING_ENRICH,
    STAGE_AFTER_LLM_ADJUDICATION,
    STAGE_AFTER_MATCH,
    STAGE_AFTER_NOISE_FILTER,
    STAGE_AFTER_RELEVANCE_FILTER,
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
from app.services.thesis_relevance_filter import filter_candidates_by_thesis_relevance

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



async def run_monitoring():
    import time
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    logger.info("Starting daily monitoring run run_id=%s", run_id)

    async with async_session() as db:
        result = await db.execute(
            select(Thesis)
            .options(selectinload(Thesis.user))
            .where(Thesis.status.in_(["active", "needs_review"]))
        )
        active_theses = result.scalars().all()

        if await _maybe_create_monitoring_inactive_event(db, active_theses):
            return

        thesis_holdings, all_tickers = await _load_thesis_holdings_and_tickers(db, active_theses)
        ticker_data = await _fetch_ticker_data(all_tickers)

        now = datetime.now(timezone.utc)

        for thesis in active_theses:
            holding = thesis_holdings.get(str(thesis.id))
            if holding is None:
                continue

            try:
                company_data = ticker_data.get(holding.ticker.upper())

                if company_data is None:
                    logger.warning("No market data for %s — skipping thesis %s", holding.ticker, thesis.id)
                    continue

                # Per-thesis coverage funnel — recorded throughout the pass and
                # persisted with the events. Mirrors check_now so the same
                # diagnostics endpoint surfaces both manual and daily runs.
                coverage = CoveragePassBuilder(
                    thesis_id=thesis.id,
                    holding_id=holding.id,
                    run_id=run_id,
                    triggered_by="monitoring_run",
                )

                # Direct ticker candidates
                candidates = generate_monitoring_candidates(
                    thesis.interpretation,
                    company_data,
                    float(holding.current_price) if holding.current_price is not None else None,
                    now=now,
                )
                coverage.record_source("qualitative_market_data", candidates_returned=len(candidates))

                # Proxy ticker candidates
                proxy_before = len(candidates)
                for proxy in _extract_proxy_tickers(thesis.interpretation):
                    proxy_ticker = proxy["ticker"].upper()
                    if proxy_ticker == holding.ticker:
                        continue
                    proxy_data = ticker_data.get(proxy_ticker)
                    if proxy_data is None:
                        continue
                    candidates.extend(
                        _generate_proxy_candidates(
                            proxy_data,
                            proxy,
                            thesis.interpretation,
                            now=now,
                        )
                    )

                if len(candidates) > proxy_before:
                    coverage.record_source("proxy_tickers", candidates_returned=len(candidates) - proxy_before)

                # EDGAR 8-K candidates (US tickers only; silently skipped for non-US)
                before_edgar = len(candidates)
                try:
                    edgar_filings = await get_recent_8k_filings(holding.ticker)
                    candidates.extend(build_edgar_candidates(holding.ticker, edgar_filings))
                    coverage.record_source("edgar_8k", candidates_returned=len(candidates) - before_edgar)
                except Exception as exc:
                    logger.warning("EDGAR gap for thesis %s: %s", thesis.id, exc)
                    await write_monitoring_gap(db, thesis.id, "edgar", str(exc), run_id)
                    coverage.record_source("edgar_8k", candidates_returned=0, error=str(exc))

                # EDGAR Form 4 insider transactions
                before_form4 = len(candidates)
                form4_txns = await get_recent_form4_transactions(holding.ticker)
                candidates.extend(build_form4_candidates(holding.ticker, form4_txns, now=now))
                coverage.record_source("edgar_form4", candidates_returned=len(candidates) - before_form4)

                # Enrich earnings 8-Ks (item 2.02) with LLM-extracted content
                candidates = await enrich_earnings_candidates(candidates, thesis)

                # Signal linking: load decomposition and enrich candidates
                decomposition = await load_active_decomposition(db, thesis.id)
                claims = decomposition.claims if decomposition else None

                # Gemini news uses signal descriptors from decomposition so
                # focused retrieval can include claim/rationale context.
                signal_descriptors = signal_search_descriptors_from_claims(claims)
                before_gemini = len(candidates)
                try:
                    gemini_candidates = await collect_news_evidence(
                        holding.ticker, holding.name or holding.ticker, signal_descriptors
                    )
                    candidates.extend(gemini_candidates)
                    coverage.record_source("gemini_news", candidates_returned=len(candidates) - before_gemini)
                except Exception as exc:
                    logger.warning("Gemini gap for thesis %s: %s", thesis.id, exc)
                    await write_monitoring_gap(db, thesis.id, "gemini_news", str(exc), run_id)
                    coverage.record_source("gemini_news", candidates_returned=0, error=str(exc))
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

                # Drop candidates whose event date predates this thesis — guards
                # new users against stale evidence (transcript window is 120 days).
                candidates = apply_thesis_floor(candidates, thesis.created_at)
                coverage.record_stage(STAGE_AFTER_THESIS_FLOOR, len(candidates))

                # Update price and timestamp — always runs, even on quiet passes.
                if company_data and company_data.current_price is not None:
                    await apply_market_price(
                        holding,
                        native_price=company_data.current_price,
                        native_currency=getattr(company_data, "currency", None),
                        now=now,
                    )
                holding.last_monitored_at = now

                if not candidates:
                    # Persist the funnel even on quiet passes so the user can
                    # see "we tried these sources, they had nothing today."
                    coverage.record_stage(STAGE_AFTER_NOISE_FILTER, 0)
                    coverage.record_stage(STAGE_AFTER_CLASSIFICATION, 0)
                    coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
                    coverage.record_events_persisted(0)
                    await coverage.persist(db)
                    score, new_label, prev_label = await refresh_thesis_health(
                        db, thesis, claims, decomposition, now=now
                    )
                    if thesis.user and thesis.user.email:
                        await maybe_notify_band_drop(
                            user_email=thesis.user.email,
                            ticker=holding.ticker,
                            prev_label=prev_label,
                            new_label=new_label,
                            score=score,
                        )
                    continue

                # Build lookup tables — only needed when there are candidates to classify.
                claims_by_id, signals_by_id = build_claim_signal_lookup(claims)
                investor_profile = await load_investor_profile(db, thesis.user_id)

                # Qualitative news_watch matching — BEFORE noise filtering, so a
                # matched news item is tagged (and survives minimum-relevance).
                nw_matched = await match_thesis_news_watches(candidates, extract_news_watches(claims))

                # Noise suppression: filter before classification (rules 1, 2, 4)
                candidates = await filter_candidates(candidates, holding.id, signals_by_id, db, now=now)
                coverage.record_stage(STAGE_AFTER_NOISE_FILTER, len(candidates))

                classified = await classify_candidates_for_thesis(
                    thesis,
                    candidates,
                    investor_profile=investor_profile,
                    sector=holding.sector,
                    ticker=holding.ticker,
                    company_name=holding.name,
                    nw_matched=nw_matched,
                )

                # Rule 3: Priority suppression (post-classification)
                suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
                surviving_set = {id(c) for c, _ in suppressed}
                classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]
                coverage.record_stage(STAGE_AFTER_CLASSIFICATION, len(classified))

                status_before = thesis.status
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

                # Real-time break alert: the moment a thesis flips to needs_review on
                # a breaking signal, email the user instead of waiting for the digest.
                if thesis.status == "needs_review" and status_before in ("active", "draft"):
                    breaking = next(((c, a) for c, s, a in classified if s == "thesis_breaking"), None)
                    if breaking is not None:
                        candidate, analysis = breaking
                        from app.services.alerts import maybe_send_thesis_break_alert

                        await maybe_send_thesis_break_alert(
                            user=thesis.user,
                            ticker=holding.ticker,
                            summary=analysis or candidate.get("description"),
                        )

                score, new_label, prev_label = await refresh_thesis_health(
                    db, thesis, claims, decomposition, now=now
                )
                if thesis.user and thesis.user.email:
                    await maybe_notify_band_drop(
                        user_email=thesis.user.email,
                        ticker=holding.ticker,
                        prev_label=prev_label,
                        new_label=new_label,
                        score=score,
                    )

            except Exception as e:
                logger.error("Monitoring failed for thesis %s: %s", thesis.id, e, exc_info=True)
                continue

        await db.commit()

    elapsed = time.monotonic() - started
    logger.info(
        "Daily monitoring run complete — %d theses processed in %.1fs",
        len(active_theses),
        elapsed,
    )
