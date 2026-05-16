import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.monitoring_event import MonitoringEvent
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.market_data import CompanyData, fetch_company_data, shortlist_qualitative_candidates
from app.services.ai_monitor import classify_event
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

MAX_MONITORED_POSITIONS = 50


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
        getattr(proxy_data, "insider_transactions", []),
        now=now,
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


async def run_monitoring():
    logger.info("Starting daily monitoring run")

    async with async_session() as db:
        result = await db.execute(
            select(Thesis)
            .where(Thesis.status.in_(["active", "needs_review"]))
            .limit(MAX_MONITORED_POSITIONS)
        )
        active_theses = result.scalars().all()

        if not settings.alpha_vantage_api_key and active_theses:
            # Only create a warning event if one doesn't already exist from today
            existing = await db.execute(
                select(MonitoringEvent)
                .where(MonitoringEvent.event_type == "monitoring_inactive")
                .where(MonitoringEvent.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0))
                .limit(1)
            )
            if existing.scalar_one_or_none() is None:
                first_thesis = active_theses[0]
                holding_result = await db.execute(
                    select(Holding).where(Holding.id == first_thesis.holding_id)
                )
                holding = holding_result.scalar_one_or_none()
                if holding is not None:
                    event = MonitoringEvent(
                        holding_id=holding.id,
                        thesis_id=first_thesis.id,
                        event_type="monitoring_inactive",
                        severity="info",
                        title="Monitoring is not active",
                        summary="No Alpha Vantage API key is configured. Set ALPHA_VANTAGE_API_KEY in your .env to enable market data monitoring.",
                        ai_analysis=None,
                        raw_data={"reason": "missing_alpha_vantage_api_key"},
                    )
                    db.add(event)
                    await db.commit()
            logger.warning("No Alpha Vantage API key configured — monitoring skipped")
            return

        # Phase 1: Collect all unique tickers (direct + proxy)
        thesis_holdings: dict[str, Holding] = {}  # thesis_id -> Holding
        all_tickers: set[str] = set()

        for thesis in active_theses:
            holding_result = await db.execute(
                select(Holding).where(Holding.id == thesis.holding_id)
            )
            holding = holding_result.scalar_one_or_none()
            if holding is None:
                continue
            thesis_holdings[str(thesis.id)] = holding
            all_tickers.add(holding.ticker.upper())

            for proxy in _extract_proxy_tickers(thesis.interpretation):
                proxy_ticker = proxy["ticker"].upper()
                if proxy_ticker != holding.ticker:
                    all_tickers.add(proxy_ticker)

        # Phase 2: Batch-fetch company data for all unique tickers
        ticker_data: dict[str, CompanyData | None] = {}
        for ticker in all_tickers:
            try:
                ticker_data[ticker] = await fetch_company_data(ticker)
            except Exception as e:
                logger.error(f"Failed to fetch data for {ticker}: {e}")
                ticker_data[ticker] = None

        # Phase 3: For each thesis, generate candidates from direct + proxy tickers
        now = datetime.now(timezone.utc)

        for thesis in active_theses:
            holding = thesis_holdings.get(str(thesis.id))
            if holding is None:
                continue

            try:
                company_data = ticker_data.get(holding.ticker.upper())

                # Direct ticker candidates
                candidates = generate_monitoring_candidates(
                    thesis.interpretation,
                    company_data,
                    float(holding.current_price) if holding.current_price is not None else None,
                    now=now,
                )

                # Proxy ticker candidates
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

                # Update holding price from direct ticker data
                if company_data and company_data.current_price is not None:
                    holding.current_price = company_data.current_price
                    holding.current_value = float(holding.quantity) * company_data.current_price

                if not candidates:
                    continue

                # Noise suppression: filter before classification (rules 1, 2, 4)
                candidates = await filter_candidates(candidates, holding.id, signals_by_id, db, now=now)

                # Classify all surviving candidates
                classified: list[tuple[dict, str, str | None]] = []
                for candidate in candidates:
                    evidence = candidate.get("evidence", {})

                    # For proxy events, include the causal context so the
                    # classifier understands why this upstream signal matters
                    event_desc = candidate["description"]
                    proxy_rationale = evidence.get("proxy_rationale")
                    proxy_signal_hint = evidence.get("proxy_signal_hint")
                    if proxy_rationale:
                        event_desc += f"\nWhy this proxy matters to the thesis: {proxy_rationale}"
                    if proxy_signal_hint:
                        event_desc += f"\nWhat to look for: {proxy_signal_hint}"

                    classification = await classify_event(
                        why_own_it=thesis.why_own_it,
                        must_remain_true=thesis.must_remain_true,
                        what_would_change_my_mind=thesis.what_would_change_my_mind,
                        ai_summary=thesis.ai_summary,
                        event_description=event_desc,
                    )

                    severity = classification.severity if classification else "warning"
                    ai_analysis = classification.analysis if classification else None
                    classified.append((candidate, severity, ai_analysis))

                # Rule 3: Priority suppression (post-classification)
                suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
                surviving_set = {id(c) for c, _ in suppressed}
                classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]

                for candidate, severity, ai_analysis in classified:
                    evidence = candidate.get("evidence", {})
                    source_url = evidence.get("url")

                    # Signal linking fields
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

                    # For proxy events, include the causal rationale in the stored summary
                    stored_summary = candidate["description"]
                    proxy_rationale = evidence.get("proxy_rationale")
                    proxy_signal_hint = evidence.get("proxy_signal_hint")
                    if proxy_rationale:
                        stored_summary += f"\nWhy this matters: {proxy_rationale}"
                    if proxy_signal_hint:
                        stored_summary += f"\nWhat to look for: {proxy_signal_hint}"

                    event = MonitoringEvent(
                        holding_id=holding.id,
                        thesis_id=thesis.id,
                        event_type=candidate["event_type"],
                        severity=severity,
                        title=f"Review {holding.ticker}",
                        summary=stored_summary,
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
                    await record_signal_fired(evidence_signal_id, signals_by_id, now=now)

                    if severity == "thesis_breaking" and thesis.status == "active":
                        thesis.status = "needs_review"

            except Exception as e:
                logger.error(f"Monitoring failed for thesis {thesis.id}: {e}")
                continue

        await db.commit()

    logger.info("Daily monitoring run complete")
