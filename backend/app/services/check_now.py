from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.market_data import MAX_CURRENT_TRANSCRIPT_AGE_DAYS, fetch_company_data
from app.services.valuation import apply_market_price, compute_pnl, to_account_value
from app.services.monitoring import check_metric_watch_hints, generate_monitoring_candidates
from app.services.noise_filter import (
    apply_priority_suppression,
    apply_thesis_floor,
    filter_candidates,
)
from app.services.monitoring_gap_writer import write_monitoring_gap
from app.services.monitoring_pipeline import (
    build_claim_signal_lookup,
    classify_candidates_for_thesis,
    expand_transcript_candidates_for_signals,
    extract_news_watches,
    extract_provisional_news_watches,
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
    adjudicate_signal_matches,
    build_evidence_summary,
    enrich_candidates_with_embedding_matches,
    load_active_decomposition,
    match_candidates_to_signals,
)

logger = logging.getLogger(__name__)

RATE_LIMIT_HOURS = 4
_SQLITE_LOCK_RETRY_ATTEMPTS = 3
_SQLITE_LOCK_RETRY_DELAY_SECONDS = 0.15


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
    status: str  # completed | rate_limited | no_data
    events_created: int = 0
    next_available_at: datetime | None = None
    created_event_ids: list[uuid.UUID] = field(default_factory=list)
    snapshot: MarketSnapshot | None = None


async def _build_snapshot(
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

    # P&L via the single valuation path: value the position in GBP (current_price
    # is native, cost basis is already GBP) and diff against cost.
    cost_basis = float(holding.average_cost_basis)  # GBP
    snapshot.cost_basis = cost_basis
    value_gbp = await to_account_value(
        holding.quantity,
        company_data.current_price,
        native_currency=getattr(company_data, "currency", None) or holding.currency,
        ticker=holding.ticker,
    )
    snapshot.pnl, snapshot.pnl_pct = compute_pnl(value_gbp, holding.quantity, cost_basis)

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


def _is_sqlite_locked_error(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


async def _persist_historical_audit_state(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
    status: str,
    results: list[dict] | None | object = ...,
) -> None:
    for attempt in range(_SQLITE_LOCK_RETRY_ATTEMPTS):
        thesis = (
            await db.execute(select(Thesis).where(Thesis.id == thesis_id))
        ).scalar_one_or_none()
        if thesis is None:
            return

        thesis.historical_audit_status = status
        if results is not ...:
            thesis.historical_audit_results = results

        try:
            await db.commit()
            return
        except OperationalError as exc:
            await db.rollback()
            if not _is_sqlite_locked_error(exc) or attempt == _SQLITE_LOCK_RETRY_ATTEMPTS - 1:
                raise
            await asyncio.sleep(_SQLITE_LOCK_RETRY_DELAY_SECONDS * (attempt + 1))


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
    company_data = None
    try:
        company_data = await fetch_company_data(holding.ticker)
    except Exception:
        logger.exception("Failed to fetch market data for %s", holding.ticker)

    if company_data is None:
        logger.warning("No market data available for %s — skipping check", holding.ticker)
        return CheckNowResult(status="no_data")

    # Generate monitoring candidates
    previous_price = float(holding.current_price) if holding.current_price is not None else None
    candidates = generate_monitoring_candidates(
        thesis.interpretation,
        company_data,
        previous_price,
        now=now,
    )

    # check-now is a single user-initiated pass; tag retrieval-source failures
    # with a per-call run_id so the gap rows are grouped the same way as the
    # batch job's daily-run rows. Without this, a Gemini outage or EDGAR
    # error during an on-demand check disappears into the logs and the user
    # silently gets thinner evidence with no visibility into why.
    check_run_id = f"check_now:{uuid.uuid4()}"

    # Coverage funnel: per-source query results and per-stage candidate counts.
    # Persisted at the end of the pass so the diagnostics endpoint can answer
    # "where did our 10 candidates go?" instead of just "we created 4 events."
    coverage = CoveragePassBuilder(
        thesis_id=thesis.id,
        holding_id=holding.id,
        run_id=check_run_id,
        triggered_by="check_now",
    )
    coverage.record_source("qualitative_market_data", candidates_returned=len(candidates))

    # EDGAR 8-K candidates (US tickers only; silently skipped for non-US)
    before_edgar = len(candidates)
    try:
        edgar_filings = await get_recent_8k_filings(holding.ticker)
        candidates.extend(build_edgar_candidates(holding.ticker, edgar_filings))
        coverage.record_source("edgar_8k", candidates_returned=len(candidates) - before_edgar)
    except Exception as exc:
        logger.warning("EDGAR fetch failed for %s during check-now — skipping: %s", holding.ticker, exc)
        await write_monitoring_gap(db, thesis.id, "edgar", str(exc), check_run_id)
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

    # Gemini news uses signal descriptors from the decomposition so focused
    # searches can include claim/rationale context, not just bare labels.
    signal_descriptors = signal_search_descriptors_from_claims(claims)
    before_gemini = len(candidates)
    try:
        gemini_candidates = await collect_news_evidence(
            holding.ticker, holding.name or holding.ticker, signal_descriptors
        )
        candidates.extend(gemini_candidates)
        coverage.record_source("gemini_news", candidates_returned=len(candidates) - before_gemini)
    except Exception as exc:
        logger.warning("Gemini news failed for %s during check-now — skipping: %s", holding.ticker, exc)
        await write_monitoring_gap(db, thesis.id, "gemini_news", str(exc), check_run_id)
        coverage.record_source("gemini_news", candidates_returned=0, error=str(exc))
    coverage.record_stage(STAGE_CANDIDATES_GENERATED, len(candidates))
    candidates = match_candidates_to_signals(candidates, claims)
    coverage.record_stage(STAGE_AFTER_MATCH, len(candidates))

    # Semantic ranking layer: union embedding-based matches into the multi-
    # binding list so a candidate that didn't share words with the signal
    # label can still bind ("Pricing Dilemma" → "Services gross margin").
    # Falls back to word-overlap inside build_embedding_similarity if the
    # OpenAI embedding call fails, so this never makes the pipeline less
    # resilient than before.
    candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
    coverage.record_stage(STAGE_AFTER_EMBEDDING_ENRICH, len(candidates))
    # Adjudicate borderline embedding matches with a cheap LLM call so a
    # cosine-0.65 "maybe" becomes a concrete keep-or-drop with a real
    # confidence score the UI can show.
    candidates = await adjudicate_signal_matches(candidates, claims)
    coverage.record_stage(STAGE_AFTER_LLM_ADJUDICATION, len(candidates))

    # Thesis-aware relevance filter for news-style candidates. When Gemini
    # is up this trims polished noise (13F filings, fund-flow updates); when
    # Gemini is down it's the floor that keeps yfinance/AV news from
    # surfacing as info-tier noise. Cheap (gpt-4o-mini) per-candidate check
    # before the expensive severity classification downstream.
    if claims:
        from app.services.thesis_relevance_filter import filter_candidates_by_thesis_relevance
        candidates = await filter_candidates_by_thesis_relevance(
            candidates,
            signal_descriptors=signal_descriptors,
            ticker=holding.ticker,
            why_own_it=thesis.why_own_it or "",
        )
        coverage.record_stage(STAGE_AFTER_RELEVANCE_FILTER, len(candidates))
        # The relevance filter can attach matched signal labels after the first
        # binding pass. Re-run light signal enrichment so those new labels and
        # any semantic matches flow into multi-binding instead of getting lost.
        candidates = match_candidates_to_signals(candidates, claims)
        candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
        candidates = await adjudicate_signal_matches(candidates, claims)

    # Drop candidates predating this thesis — same guard as the daily batch run,
    # critical here because run_first_pulse fires immediately after onboarding.
    candidates = apply_thesis_floor(candidates, thesis.created_at)
    coverage.record_stage(STAGE_AFTER_THESIS_FLOOR, len(candidates))

    # Build lookup tables for narrative generation
    claims_by_id, signals_by_id = build_claim_signal_lookup(claims)
    investor_profile = await load_investor_profile(db, thesis.user_id)

    # Build snapshot — always returned, even when 0 events
    snapshot = await _build_snapshot(company_data, holding, previous_price, thesis)

    # Update holding price via the single valuation path (GBP value, not native).
    if company_data and company_data.current_price is not None:
        await apply_market_price(
            holding,
            native_price=company_data.current_price,
            native_currency=getattr(company_data, "currency", None),
            now=now,
        )

    # Record that we actually checked, even if the pass is quiet — this is what
    # lets the dashboard say "checked just now, all calm" truthfully.
    holding.last_monitored_at = now

    # Qualitative news_watch matching — BEFORE noise filtering, so a matched
    # news item is tagged (and survives minimum-relevance) and gets cooldown.
    news_watches = extract_news_watches(claims)
    if not news_watches:
        news_watches = extract_provisional_news_watches(thesis.interpretation)
    nw_matched = await match_thesis_news_watches(candidates, news_watches)

    # Per-active-signal transcript expansion: every active signal gets its
    # own transcript candidate seeded with claim + label + rationale,
    # pre-bound to the signal. This is the AMD-style segment-commentary
    # path Codex called out — previously only news_watch signals got
    # transcript candidates of their own, leaving revenue_growth /
    # earnings_growth / news_topic signals with effectively zero transcript
    # coverage even when relevant Q&A existed in the call.
    candidates = await expand_transcript_candidates_for_signals(candidates, claims)

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

    return CheckNowResult(
        status="completed",
        events_created=len(created_event_ids),
        created_event_ids=created_event_ids,
        snapshot=snapshot,
    )


MONITORABLE_THESIS_STATUSES = ("active", "draft", "needs_review")
FIRST_PULSE_MAX_HOLDINGS = 5


async def _holdings_needing_first_pulse(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None,
    limit: int,
) -> list[tuple[Holding, Thesis]]:
    """Holdings that have a monitorable thesis but have never had a real
    monitoring pass yet (so the dashboard's 'all calm' has never actually been
    verified). Ordered by position size so the biggest bets get checked first."""
    event_exists = (
        select(MonitoringEvent.id)
        .where(
            MonitoringEvent.holding_id == Holding.id,
            MonitoringEvent.event_type != "monitoring_inactive",
        )
        .correlate(Holding)
        .limit(1)
    )
    query = (
        select(Holding)
        .where(Holding.user_id == user_id)
        .where(~event_exists.exists())
        .order_by(func.coalesce(Holding.current_value, 0).desc())
        .limit(limit)
    )
    if holding_id is not None:
        query = query.where(Holding.id == holding_id)

    holdings = (await db.execute(query)).scalars().all()

    pairs: list[tuple[Holding, Thesis]] = []
    for holding in holdings:
        thesis = (
            await db.execute(
                select(Thesis)
                .where(
                    Thesis.holding_id == holding.id,
                    Thesis.user_id == user_id,
                    Thesis.status.in_(MONITORABLE_THESIS_STATUSES),
                )
                .order_by(Thesis.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if thesis is not None:
            pairs.append((holding, thesis))
    return pairs


async def _run_first_pulse_with_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None,
    limit: int,
) -> int:
    """Core of run_first_pulse, with an injected session so it's testable.
    Returns the number of holdings checked."""
    pairs = await _holdings_needing_first_pulse(
        db, user_id=user_id, holding_id=holding_id, limit=limit
    )
    pair_ids = [(holding.id, thesis.id) for holding, thesis in pairs]
    checked = 0
    for holding_id, thesis_id in pair_ids:
        try:
            holding = (
                await db.execute(select(Holding).where(Holding.id == holding_id))
            ).scalar_one_or_none()
            thesis = (
                await db.execute(select(Thesis).where(Thesis.id == thesis_id))
            ).scalar_one_or_none()
            if holding is None or thesis is None:
                continue
            await run_check_now(holding, thesis, db)
            checked += 1
        except Exception:
            # One holding failing (bad ticker, market data outage) must not stop
            # the rest — the first pulse is best-effort.
            await db.rollback()
            logger.exception("First pulse: check failed for holding %s", holding_id)
    return checked


async def run_first_pulse(
    user_id: uuid.UUID,
    holding_id: uuid.UUID | None = None,
    *,
    limit: int = FIRST_PULSE_MAX_HOLDINGS,
) -> None:
    """Run the first monitoring pass the moment a thesis becomes monitorable.

    Without this, a new user who just wrote their theses sees a dashboard that
    reports every position as "intact — your assumptions still hold" when nothing
    has actually been checked (monitoring events only appear after the next 6 AM
    job). This delivers a truthful first pulse in their very first session: a live
    snapshot plus any price/news/earnings/filing signal that already contradicts
    the thesis.

    Designed as a FastAPI BackgroundTask: opens its own DB session (like
    generate_draft_theses_for_user), is idempotent (skips any holding that already
    has a real monitoring event), and never raises.
    """
    if not settings.enable_first_pulse:
        return

    from app.database import async_session

    try:
        async with async_session() as db:
            await _run_first_pulse_with_session(
                db, user_id=user_id, holding_id=holding_id, limit=limit
            )
    except Exception:
        logger.exception("First pulse failed for user %s", user_id)


HISTORICAL_AUDIT_LOOKBACK_DAYS = 90
_AUDIT_STALE_MINUTES = 10


def _description_fingerprint(description: str) -> frozenset[str]:
    """Return a bag-of-significant-words for near-duplicate detection."""
    stop = {"the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "it",
            "at", "by", "on", "as", "with", "its", "that", "this", "was", "are"}
    words = {w.lower().strip(".,;:") for w in description.split() if len(w) > 3}
    return frozenset(words - stop)


def _serialise_audit_results(
    classified: list[tuple],
    *,
    thesis: Thesis,
    investor_profile: str | None,
    claims_by_id: dict[str, object],
    signals_by_id: dict[str, object],
) -> list[dict]:
    """Convert classified candidates into a signal-aware historical audit payload."""
    SEVERITY_ORDER = {"thesis_breaking": 0, "warning": 1, "info": 2}
    results = []
    for candidate, severity, _analysis in classified:
        evidence = candidate.get("evidence") or {}
        evidence_signal_id = evidence.get("signal_id")
        evidence_claim_id = evidence.get("claim_id")
        claim_obj = claims_by_id.get(evidence_claim_id) if evidence_claim_id else None
        signal_obj = signals_by_id.get(evidence_signal_id) if evidence_signal_id else None

        # A 90-day "value from day one" pass should surface either:
        # - events tied to a specific claim/signal, or
        # - stronger warnings/breaks that would have mattered anyway.
        # Generic info-only rows (e.g. broad analyst sentiment with no thesis link)
        # make the feature look busier than it really is.
        if claim_obj is None and signal_obj is None:
            if candidate.get("event_type") == "earnings_surprise":
                continue
            if (
                severity == "info"
                and candidate.get("event_type") in {"news_or_earnings_candidate", "product_ramp_update", "contract_renewal_update", "funding_condition_update", "margin_pressure_update", "customer_capex_signal", "gemini_news", "news_keyword_match"}
            ):
                continue
            if severity == "info":
                continue

        raw_date = (
            evidence.get("date")
            or evidence.get("filing_date")
            or evidence.get("event_date")
        )
        event_date = str(raw_date)[:10] if raw_date else None
        claim_text = getattr(claim_obj, "claim_text", None)
        signal_label = getattr(signal_obj, "signal_label", None)
        analysis = build_evidence_summary(
            candidate=candidate,
            claim_text=claim_text,
            signal_label=signal_label,
            why_own_it=thesis.why_own_it,
            severity=severity,
            verdict=None,
            investor_profile=investor_profile,
        )
        results.append({
            "description": candidate.get("description", ""),
            "severity": severity,
            "event_type": candidate.get("event_type", ""),
            "event_date": event_date,
            "signal_label": signal_label,
            "claim_text": claim_text,
            "analysis": analysis,
            "evidence": evidence,
        })

    # Deduplicate: within the same event_type+week, drop lower-severity near-duplicates.
    # Two descriptions are considered duplicates when they share ≥60% of significant words.
    def _week_bucket(date_str: str | None) -> str:
        if not date_str:
            return "unknown"
        try:
            d = datetime.fromisoformat(date_str)
            return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
        except ValueError:
            return "unknown"

    results.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 3))
    seen: list[dict] = []
    for item in results:
        fp = _description_fingerprint(item["description"])
        bucket = (item["event_type"], _week_bucket(item.get("event_date")))
        duplicate = False
        for kept in seen:
            if (kept["event_type"], _week_bucket(kept.get("event_date"))) == bucket:
                kept_fp = _description_fingerprint(kept["description"])
                union = fp | kept_fp
                if union and len(fp & kept_fp) / len(union) >= 0.6:
                    duplicate = True
                    break
        if not duplicate:
            seen.append(item)

    def _safe_ts(date_str: str | None) -> float:
        if not date_str:
            return 0.0
        try:
            return datetime.fromisoformat(date_str).timestamp()
        except ValueError:
            return 0.0

    seen.sort(
        key=lambda r: (
            SEVERITY_ORDER.get(r["severity"], 3),
            -_safe_ts(r.get("event_date")),
        )
    )
    return seen


def _build_coverage_gap_items(
    *,
    thesis: Thesis,
    candidates: list[dict],
    nw_matched: dict[int, tuple[object, str, str]] | None,
    signals_by_id: dict[str, object],
) -> list[dict]:
    """Return an informational audit row when source coverage looks thin.

    This is intentionally conservative and only fires when a thesis has active
    qualitative signals but the 90-day pass surfaced no candidate tied to them.
    That lets the UI distinguish:
    - "No signal fired" from
    - "We do not yet have strong enough news/transcript coverage for this shape"
    """
    qualitative_types = {"news_topic", "transcript_topic", "news_watch"}
    active_qualitative = [
        sig
        for sig in signals_by_id.values()
        if getattr(sig, "active", False) and getattr(sig, "signal_type", None) in qualitative_types
    ]
    provisional_labels: list[str] = []
    if not active_qualitative:
        watch_hints = (thesis.interpretation or {}).get("watch_hints")
        if isinstance(watch_hints, list):
            provisional_labels = [
                str(hint.get("label") or hint.get("watch_for") or "").strip()
                for hint in watch_hints
                if isinstance(hint, dict) and hint.get("kind") == "news_watch"
            ]
            provisional_labels = [label for label in provisional_labels if label]
        if not provisional_labels:
            return []

    linked_signal_ids: set[str] = set()
    for candidate in candidates:
        evidence = candidate.get("evidence") or {}
        signal_id = evidence.get("signal_id")
        if signal_id:
            linked_signal_ids.add(str(signal_id))

    for watch, _severity, _reason in (nw_matched or {}).values():
        signal_id = getattr(watch, "signal_id", None)
        if signal_id:
            linked_signal_ids.add(str(signal_id))

    uncovered = [sig for sig in active_qualitative if str(sig.id) not in linked_signal_ids]
    if uncovered:
        labels = [
            getattr(sig, "signal_label", None) or getattr(sig, "signal_type", "qualitative signal")
            for sig in uncovered
        ]
    else:
        labels = provisional_labels
    if not labels:
        return []

    preview = ", ".join(labels[:2])
    if len(labels) > 2:
        preview = f"{preview}, and {len(labels) - 2} more"

    return [
        {
            "description": "Coverage is still thin for some active qualitative signals.",
            "severity": "info",
            "event_type": "coverage_gap",
            "event_date": None,
            "signal_label": None,
            "claim_text": None,
            "analysis": (
                "No active signal fired in the last 90 days, but this audit also did not surface "
                f"claim-linked news or transcript evidence for: {preview}."
            ),
            "evidence": {"uncovered_signal_labels": labels[:5]},
        }
    ]


async def _run_historical_audit_with_session(
    db: AsyncSession,
    *,
    thesis_id: uuid.UUID,
) -> None:
    thesis = (
        await db.execute(select(Thesis).where(Thesis.id == thesis_id))
    ).scalar_one_or_none()
    if thesis is None:
        return

    holding = (
        await db.execute(select(Holding).where(Holding.id == thesis.holding_id))
    ).scalar_one_or_none()
    if holding is None:
        await _persist_historical_audit_state(db, thesis_id=thesis_id, status="failed")
        return

    if thesis.historical_audit_status == "ready":
        return
    if thesis.historical_audit_status == "pending":
        updated = thesis.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - updated) < timedelta(minutes=_AUDIT_STALE_MINUTES):
            return

    await _persist_historical_audit_state(db, thesis_id=thesis_id, status="pending")

    now = datetime.now(timezone.utc)
    # apply_thesis_floor uses floor = anchor - timedelta(days=1) internally.
    # Passing now - (LOOKBACK - 1) days gives an effective floor of now - LOOKBACK days.
    audit_floor_anchor = now - timedelta(days=HISTORICAL_AUDIT_LOOKBACK_DAYS - 1)

    try:
        company_data = await fetch_company_data(holding.ticker)
        if company_data is None:
            await _persist_historical_audit_state(db, thesis_id=thesis_id, status="empty")
            return

        previous_price = float(holding.current_price) if holding.current_price is not None else None
        candidates = generate_monitoring_candidates(
            thesis.interpretation,
            company_data,
            previous_price,
            now=now,
            transcript_max_age_days=MAX_CURRENT_TRANSCRIPT_AGE_DAYS,
        )

        # Tag retrieval failures with a per-audit run_id so users see the gap
        # rows the same way as for live check-now / daily jobs.
        audit_run_id = f"historical_audit:{uuid.uuid4()}"
        coverage = CoveragePassBuilder(
            thesis_id=thesis.id,
            holding_id=holding.id,
            run_id=audit_run_id,
            triggered_by="historical_audit",
        )
        coverage.record_source("qualitative_market_data", candidates_returned=len(candidates))

        try:
            audit_since = (now - timedelta(days=HISTORICAL_AUDIT_LOOKBACK_DAYS)).date()
            edgar_filings = await get_recent_8k_filings(holding.ticker, since=audit_since)
            before_edgar = len(candidates)
            candidates.extend(build_edgar_candidates(holding.ticker, edgar_filings))
            coverage.record_source("edgar_8k", candidates_returned=len(candidates) - before_edgar)
        except Exception as exc:
            logger.warning("EDGAR fetch failed for %s in historical audit: %s", holding.ticker, exc)
            await write_monitoring_gap(db, thesis.id, "edgar", str(exc), audit_run_id)
            coverage.record_source("edgar_8k", candidates_returned=0, error=str(exc))

        decomposition = await load_active_decomposition(db, thesis.id)
        claims = decomposition.claims if decomposition else None
        signal_descriptors = signal_search_descriptors_from_claims(claims)

        try:
            before_gemini = len(candidates)
            gemini_candidates = await collect_news_evidence(
                holding.ticker, holding.name or holding.ticker, signal_descriptors,
                days_back=HISTORICAL_AUDIT_LOOKBACK_DAYS,
            )
            candidates.extend(gemini_candidates)
            coverage.record_source("gemini_news", candidates_returned=len(candidates) - before_gemini)
        except Exception as exc:
            logger.warning("Gemini news failed for %s in historical audit: %s", holding.ticker, exc)
            await write_monitoring_gap(db, thesis.id, "gemini_news", str(exc), audit_run_id)
            coverage.record_source("gemini_news", candidates_returned=0, error=str(exc))

        # Form 4 insider transactions and earnings enrichment are intentionally omitted —
        # they add LLM cost per filing over a 90-day window. The live pipeline handles them.
        coverage.record_stage(STAGE_CANDIDATES_GENERATED, len(candidates))
        candidates = match_candidates_to_signals(candidates, claims)
        coverage.record_stage(STAGE_AFTER_MATCH, len(candidates))
        candidates = await enrich_candidates_with_embedding_matches(candidates, claims)
        coverage.record_stage(STAGE_AFTER_EMBEDDING_ENRICH, len(candidates))
        candidates = await adjudicate_signal_matches(candidates, claims)
        coverage.record_stage(STAGE_AFTER_LLM_ADJUDICATION, len(candidates))
        if claims:
            from app.services.thesis_relevance_filter import filter_candidates_by_thesis_relevance

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
        candidates = apply_thesis_floor(candidates, audit_floor_anchor)
        coverage.record_stage(STAGE_AFTER_THESIS_FLOOR, len(candidates))

        claims_by_id, signals_by_id = build_claim_signal_lookup(claims)
        investor_profile = await load_investor_profile(db, thesis.user_id)

        news_watches = extract_news_watches(claims)
        if not news_watches:
            news_watches = extract_provisional_news_watches(thesis.interpretation)
        nw_matched = await match_thesis_news_watches(candidates, news_watches)

        candidates = await filter_candidates(
            candidates, holding.id, signals_by_id, db, now=now, skip_cooldown=True
        )
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

        suppressed = apply_priority_suppression([(c, s) for c, s, _ in classified])
        surviving_set = {id(c) for c, _ in suppressed}
        classified = [(c, s, a) for c, s, a in classified if id(c) in surviving_set]
        coverage.record_stage(STAGE_AFTER_CLASSIFICATION, len(classified))
        coverage.record_stage(STAGE_EVENTS_PERSISTED, 0)
        coverage.record_events_persisted(0)
        await coverage.persist(db)

        results = _serialise_audit_results(
            classified,
            thesis=thesis,
            investor_profile=investor_profile,
            claims_by_id=claims_by_id,
            signals_by_id=signals_by_id,
        )
        if not results:
            results = _build_coverage_gap_items(
                thesis=thesis,
                candidates=candidates,
                nw_matched=nw_matched,
                signals_by_id=signals_by_id,
            )

        await _persist_historical_audit_state(
            db,
            thesis_id=thesis_id,
            status="ready" if results else "empty",
            results=results,
        )

    except Exception:
        logger.exception("Historical audit pipeline failed for thesis %s", thesis_id)
        try:
            await _persist_historical_audit_state(db, thesis_id=thesis_id, status="failed")
        except Exception:
            pass


async def run_historical_audit(thesis_id: uuid.UUID) -> None:
    """Run a 90-day historical monitoring pass for a newly confirmed thesis.

    Stores results in thesis.historical_audit_results without persisting
    MonitoringEvents — the live feed stays clean. Designed as a BackgroundTask.
    """
    # Reuses the first-pulse flag — both features share the same API-cost profile
    # (live market data + Gemini call per thesis). Disabling one disables both.
    if not settings.enable_first_pulse:
        return

    from app.database import async_session

    try:
        async with async_session() as db:
            await _run_historical_audit_with_session(db, thesis_id=thesis_id)
    except Exception:
        logger.exception("Historical audit failed for thesis %s", thesis_id)
