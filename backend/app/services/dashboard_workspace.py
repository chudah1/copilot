from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conviction_log_entry import ConvictionLogEntry
from app.models.decision_snapshot import DecisionSnapshot
from app.models.holding import Holding
from app.models.onboarding_draft import OnboardingDraft
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.user import User
from app.schemas.dashboard import (
    DashboardBlindSpotResponse,
    DashboardDecisionMemoryResponse,
    DashboardDecisionPatternResponse,
    DashboardPortfolioStateResponse,
    DashboardRecentDecisionResponse,
    DashboardSummaryMetricsResponse,
    DashboardWorkspaceItemResponse,
    DashboardWorkspaceResponse,
)
from app.schemas.holding import HoldingResponse
from app.services.conviction_log import (
    EVIDENCE_REVIEWED,
    POST_EARNINGS_REVIEW,
    QUARTERLY_REVIEW,
    REASON_INVALIDATED,
    REASON_UPDATED,
)
from app.services.case_state import (
    age_in_days,
    classify_case_quality,
    get_case_review_pressure,
    read_ambiguity_note,
    read_monitorability,
)
from app.services.decision_mirror import get_decision_patterns
from app.services.display_currency import get_display_currency_context, serialize_holdings
from app.services.pulse import HoldingPulse, compute_portfolio_pulse


@dataclass
class _DecisionState:
    kind: str
    priority: int


@dataclass
class _CaseQuality:
    kind: str
    rank: int
    days_old: int | None
    cadence_days: int | None


@dataclass
class _WorkspaceEntry:
    holding: HoldingResponse
    thesis: Thesis | None
    pulse: HoldingPulse | None
    decision_state: _DecisionState
    case_quality: _CaseQuality


def _age_in_days(date_value: datetime | None, *, now: datetime) -> int | None:
    return age_in_days(date_value, now=now)


def _decision_state(*, thesis: Thesis | None, pulse: HoldingPulse | None) -> _DecisionState:
    if thesis is None or not (thesis.why_own_it or "").strip():
        return _DecisionState(kind="needs_written_case", priority=2)
    if ((pulse and pulse.pulse_basis != "case_review" and pulse.pulse_status == "review") or thesis.status == "needs_review"):
        return _DecisionState(kind="needs_decision", priority=0)
    if pulse and pulse.pulse_basis != "case_review" and pulse.pulse_status == "watch":
        return _DecisionState(kind="changed", priority=1)
    return _DecisionState(kind="calm", priority=3)


def _monitorability(thesis: Thesis | None) -> str | None:
    return read_monitorability(thesis)


def _ambiguity_note(thesis: Thesis | None) -> str:
    return read_ambiguity_note(thesis)


def _review_pressure(thesis: Thesis | None, *, now: datetime) -> str | None:
    pressure = get_case_review_pressure(thesis, now=now)
    return pressure.level if pressure is not None else None


def _classify_case_quality(thesis: Thesis | None, *, now: datetime) -> _CaseQuality:
    quality = classify_case_quality(thesis, now=now)
    return _CaseQuality(
        kind=quality.kind,
        rank=quality.rank,
        days_old=quality.days_old,
        cadence_days=quality.cadence_days,
    )


def _holding_value(holding: HoldingResponse) -> float:
    if holding.current_value is not None:
        return float(holding.current_value)
    return float(holding.quantity) * float(holding.average_cost_basis)


def _compare_entries(entry: _WorkspaceEntry) -> tuple[int, int, int, float]:
    return (
        entry.decision_state.priority,
        -(entry.pulse.urgency_score if entry.pulse else 0),
        entry.case_quality.rank,
        -_holding_value(entry.holding),
    )


def _blind_spot_reason(entry: _WorkspaceEntry) -> str:
    if entry.case_quality.kind == "missing":
        return "No written position view yet."
    if entry.case_quality.kind == "weak":
        return "The current position view is still too vague to monitor with confidence."
    if entry.case_quality.kind == "review_overdue":
        cadence = entry.case_quality.cadence_days or 30
        days_old = entry.case_quality.days_old or 0
        return f"This position view is {days_old} days old and outside its {cadence}-day review cadence."
    return "The current position view works, but still needs sharper break conditions."


async def _load_recent_decisions(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    limit: int = 5,
) -> list[DashboardRecentDecisionResponse]:
    interesting_types = [
        EVIDENCE_REVIEWED,
        POST_EARNINGS_REVIEW,
        QUARTERLY_REVIEW,
        REASON_UPDATED,
        REASON_INVALIDATED,
    ]
    rows = (
        await db.execute(
            select(ConvictionLogEntry, Holding.ticker, Holding.name)
            .join(Holding, Holding.id == ConvictionLogEntry.holding_id)
            .where(
                ConvictionLogEntry.user_id == user_id,
                ConvictionLogEntry.entry_type.in_(interesting_types),
            )
            .order_by(ConvictionLogEntry.created_at.desc())
            # Pull a small buffer so duplicate writes do not crowd an older,
            # distinct decision out of the dashboard preview.
            .limit(limit * 3)
        )
    ).all()

    results: list[DashboardRecentDecisionResponse] = []
    seen_keys: set[tuple] = set()
    for entry, ticker, name in rows:
        metadata = entry.metadata_json or {}
        action = metadata.get("action") if isinstance(metadata, dict) else None
        assumption_label = None
        if isinstance(metadata, dict):
            raw = metadata.get("signal_label") or metadata.get("assumption_label")
            if isinstance(raw, str) and raw.strip():
                assumption_label = raw.strip()
        content_key = " ".join((entry.content or "").split()).casefold()
        dedupe_key = (
            entry.holding_id,
            entry.entry_type,
            action if isinstance(action, str) else None,
            assumption_label,
            content_key,
            entry.created_at.date() if entry.created_at else None,
        )
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        results.append(
            DashboardRecentDecisionResponse(
                holding_id=entry.holding_id,
                thesis_id=entry.thesis_id,
                ticker=ticker,
                name=name,
                entry_type=entry.entry_type,
                action=action if isinstance(action, str) else None,
                assumption_label=assumption_label,
                content=entry.content,
                created_at=entry.created_at,
            )
        )
        if len(results) >= limit:
            break
    return results


async def _load_decision_memory(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> DashboardDecisionMemoryResponse:
    patterns_payload = await get_decision_patterns(db, user_id, min_instances=3)
    raw_patterns = patterns_payload.get("patterns", [])
    resolved_count = int(patterns_payload.get("resolved_count", 0) or 0)

    open_followup_rows = (
        await db.execute(
            select(DecisionSnapshot.id).where(
                DecisionSnapshot.user_id == user_id,
                DecisionSnapshot.resolved_at.is_(None),
            )
        )
    ).scalars().all()
    open_followups_count = len(open_followup_rows)

    patterns = [
        DashboardDecisionPatternResponse(
            kind=str(pattern.get("kind", "pattern")),
            tone=str(pattern.get("tone", "neutral")),
            headline=str(pattern.get("headline", "")),
            detail=str(pattern.get("detail", "")),
            instances=int(pattern.get("instances", 0) or 0),
            hits=int(pattern.get("hits", 0) or 0),
        )
        for pattern in raw_patterns
    ]

    primary_pattern = patterns[0] if patterns else None
    return DashboardDecisionMemoryResponse(
        resolved_count=resolved_count,
        open_followups_count=open_followups_count,
        has_pattern=primary_pattern is not None,
        primary_pattern=primary_pattern,
        secondary_patterns=patterns[1:3],
    )


async def build_dashboard_workspace(db: AsyncSession, *, user: User) -> DashboardWorkspaceResponse:
    now = datetime.now().astimezone()

    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.current_value.desc().nulls_last())
    )
    raw_holdings = list(holdings_result.scalars().all())

    display = await get_display_currency_context(user)
    holdings = serialize_holdings(raw_holdings, display)
    holdings_by_id = {holding.id: holding for holding in holdings}

    holding_ids = [holding.id for holding in raw_holdings]
    theses_by_holding: dict[uuid.UUID, Thesis] = {}
    if holding_ids:
        theses_result = await db.execute(
            select(Thesis).where(
                Thesis.user_id == user.id,
                Thesis.holding_id.in_(holding_ids),
                Thesis.status.in_(["draft", "active", "needs_review"]),
            ).order_by(Thesis.created_at.desc())
        )
        for thesis in theses_result.scalars().all():
            theses_by_holding.setdefault(thesis.holding_id, thesis)

    pulses, _next_digest_at = await compute_portfolio_pulse(user.id, db)
    pulses_by_holding = {pulse.holding_id: pulse for pulse in pulses}

    entries = [
        _WorkspaceEntry(
            holding=holding,
            thesis=theses_by_holding.get(holding.id),
            pulse=pulses_by_holding.get(holding.id),
            decision_state=_decision_state(
                thesis=theses_by_holding.get(holding.id),
                pulse=pulses_by_holding.get(holding.id),
            ),
            case_quality=_classify_case_quality(
                theses_by_holding.get(holding.id),
                now=now,
            ),
        )
        for holding in holdings
    ]
    entries.sort(key=_compare_entries)

    attention_entries = [entry for entry in entries if entry.decision_state.kind in {"needs_decision", "changed"}]
    blind_spot_entries = [
        entry
        for entry in entries
        if entry.case_quality.kind in {"missing", "weak", "review_overdue", "workable"}
    ]
    blind_spot_entries.sort(key=lambda entry: (entry.case_quality.rank, -_holding_value(entry.holding)))

    draft_rows = (
        await db.execute(
            select(OnboardingDraft.status).where(OnboardingDraft.user_id == user.id)
        )
    ).scalars().all()
    drafts_ready_count = sum(1 for status in draft_rows if status == "ready")
    drafts_pending_count = sum(1 for status in draft_rows if status == "pending")

    state_result = await db.execute(select(OnboardingState).where(OnboardingState.user_id == user.id))
    onboarding_state = state_result.scalar_one_or_none()

    total_value = sum(_holding_value(holding) for holding in holdings)
    total_cost = sum(float(holding.quantity) * float(holding.average_cost_basis) for holding in holdings)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    monitored_count = sum(1 for entry in entries if entry.thesis is not None)
    needs_decision_count = sum(1 for entry in entries if entry.decision_state.kind == "needs_decision")
    changed_count = sum(1 for entry in entries if entry.decision_state.kind == "changed")
    needs_written_case_count = sum(1 for entry in entries if entry.decision_state.kind == "needs_written_case")

    top_entry = entries[0] if entries else None

    def to_workspace_item(entry: _WorkspaceEntry) -> DashboardWorkspaceItemResponse:
        return DashboardWorkspaceItemResponse(
            holding=entry.holding,
            thesis_id=entry.thesis.id if entry.thesis else None,
            decision_state=entry.decision_state.kind,
            case_quality=entry.case_quality.kind,
            pulse_status=entry.pulse.pulse_status if entry.pulse else None,
            pulse_basis=entry.pulse.pulse_basis if entry.pulse else None,
            assumption_label=entry.pulse.assumption_label if entry.pulse else None,
            reason=(entry.pulse.reason if entry.pulse else None) or _blind_spot_reason(entry),
            latest_event_summary=entry.pulse.latest_event_summary if entry.pulse else None,
            urgency_score=entry.pulse.urgency_score if entry.pulse else 0,
            days_since_thesis_update=entry.pulse.days_since_thesis_update if entry.pulse else entry.case_quality.days_old,
            review_cadence_days=entry.thesis.review_cadence_days if entry.thesis else None,
        )

    workspace = DashboardWorkspaceResponse(
        investor_profile=onboarding_state.investor_profile if onboarding_state else None,
        portfolio_state=DashboardPortfolioStateResponse(
            kind=(
                "needs_decision" if needs_decision_count > 0
                else "changed" if changed_count > 0
                else "needs_written_case" if needs_written_case_count > 0
                else "calm"
            ),
            primary_holding_id=top_entry.holding.id if top_entry else None,
            primary_ticker=top_entry.holding.ticker if top_entry else None,
            assumption_label=top_entry.pulse.assumption_label if top_entry and top_entry.pulse else None,
            needs_decision_count=needs_decision_count,
            changed_count=changed_count,
            needs_written_case_count=needs_written_case_count,
        ),
        summary_metrics=DashboardSummaryMetricsResponse(
            total_value=round(total_value, 2),
            total_cost=round(total_cost, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            portfolio_currency=display.portfolio_currency,
            preferred_currency=display.requested_currency,
            fx_unavailable=display.fx_unavailable,
            holdings_count=len(holdings),
            monitored_count=monitored_count,
            needs_decision_count=needs_decision_count,
            changed_count=changed_count,
            needs_written_case_count=needs_written_case_count,
            drafts_ready_count=drafts_ready_count,
            drafts_pending_count=drafts_pending_count,
        ),
        top_decision=to_workspace_item(top_entry) if top_entry else None,
        watchlist=[to_workspace_item(entry) for entry in attention_entries[:5]],
        blind_spots=[
            DashboardBlindSpotResponse(
                holding=entry.holding,
                thesis_id=entry.thesis.id if entry.thesis else None,
                blind_spot_kind=entry.case_quality.kind,
                reason=_blind_spot_reason(entry),
                review_cadence_days=entry.thesis.review_cadence_days if entry.thesis else None,
                days_since_thesis_update=entry.case_quality.days_old,
            )
            for entry in blind_spot_entries[:5]
        ],
        recent_decisions=await _load_recent_decisions(db, user_id=user.id),
        decision_memory=await _load_decision_memory(db, user_id=user.id),
    )
    # keep forward-compatible for the frontend migration
    workspace.summary_metrics.total_value = round(workspace.summary_metrics.total_value, 2)
    return workspace
