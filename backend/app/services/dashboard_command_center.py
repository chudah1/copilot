from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.holding import Holding
from app.models.onboarding_draft import OnboardingDraft
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.models.user import User
from app.schemas.dashboard import (
    DashboardCommandCenterHoldingResponse,
    DashboardCommandCenterResponse,
    DashboardCommandCenterSectionResponse,
    DashboardCommandCenterSummaryResponse,
)
from app.schemas.holding import HoldingResponse
from app.services.case_state import classify_case_quality
from app.services.display_currency import get_display_currency_context, serialize_holdings
from app.services.open_loops import list_open_loops
from app.services.pulse import HoldingPulse, compute_portfolio_pulse
from app.services.support_evidence import (
    SupportingItem,
    curate_supporting_items,
    load_supporting_events_for_holdings,
)


ACTIVE_THESIS_STATUSES = ("draft", "active", "needs_review")
COMMAND_CENTER_MAX_ITEMS = 5


@dataclass
class _WorkflowState:
    kind: str
    label: str
    priority: int
    reason: str
    cta_label: str
    cta_href: str


@dataclass
class _HoldingContext:
    holding: HoldingResponse
    thesis: Thesis | None
    pulse: HoldingPulse | None
    case_quality_kind: str
    case_quality_rank: int
    days_since_thesis_update: int | None
    draft: OnboardingDraft | None
    has_pending_signal_confirmation: bool
    supporting: SupportingItem | None
    loops: list
    workflow: _WorkflowState


def _holding_value(holding: HoldingResponse) -> float:
    if holding.current_value is not None:
        return float(holding.current_value)
    return float(holding.quantity) * float(holding.average_cost_basis)


def _sort_key(context: _HoldingContext) -> tuple[int, int, int, float]:
    return (
        context.workflow.priority,
        -(context.pulse.urgency_score if context.pulse else 0),
        context.case_quality_rank,
        -_holding_value(context.holding),
    )


def _pending_signal_confirmation(decomposition: ThesisDecomposition | None) -> bool:
    if decomposition is None:
        return False
    if decomposition.status == "partially_confirmed":
        return True
    for claim in decomposition.claims or []:
        for entity in claim.entities or []:
            if entity.confirmation_required and entity.user_confirmed is None:
                return True
            for signal in entity.signals or []:
                if signal.confirmation_required and signal.user_confirmed is None:
                    return True
    return False


def _build_workflow_state(
    *,
    holding: HoldingResponse,
    thesis: Thesis | None,
    pulse: HoldingPulse | None,
    case_quality,
    draft: OnboardingDraft | None,
    has_pending_signal_confirmation: bool,
    loops: list,
) -> _WorkflowState:
    ticker = holding.ticker
    has_decision_loop = any(getattr(loop, "loop_type", "") in {"claim_review", "quarterly_unsure"} for loop in loops)
    has_review_debt_loop = any(getattr(loop, "loop_type", "") == "review_overdue" for loop in loops)

    if draft is not None and draft.status == "ready":
        return _WorkflowState(
            kind="draft_ready",
            label="Draft ready",
            priority=1,
            reason="An AI draft is waiting for review before monitoring should take over.",
            cta_label="Review draft",
            cta_href="/onboarding/review-drafts",
        )

    if thesis is None or not (thesis.why_own_it or "").strip():
        return _WorkflowState(
            kind="no_thesis",
            label="No thesis",
            priority=0,
            reason="This position still needs a written case before the product can help you judge what changed.",
            cta_label="Write thesis",
            cta_href=f"/dashboard/positions/{ticker}?tab=thesis",
        )

    if has_pending_signal_confirmation:
        return _WorkflowState(
            kind="signals_unconfirmed",
            label="Signals need confirmation",
            priority=2,
            reason="The watchlist exists, but you still need to confirm what should actually be monitored.",
            cta_label="Confirm signals",
            cta_href=f"/dashboard/positions/{ticker}?tab=signals",
        )

    if thesis.status == "needs_review" or has_decision_loop or (
        pulse and pulse.pulse_basis != "case_review" and pulse.pulse_status == "review"
    ):
        return _WorkflowState(
            kind="decision_needed",
            label="Decision needed",
            priority=3,
            reason=(pulse.reason if pulse else None) or "Something important changed and this position needs an explicit call.",
            cta_label="Review position",
            cta_href=f"/dashboard/positions/{ticker}?tab=monitoring",
        )

    if pulse and pulse.pulse_basis != "case_review" and pulse.pulse_status == "watch":
        return _WorkflowState(
            kind="pressure_building",
            label="Pressure building",
            priority=4,
            reason=pulse.reason or "Nothing looks broken yet, but a pillar is being tested.",
            cta_label="See what changed",
            cta_href=f"/dashboard/positions/{ticker}?tab=monitoring",
        )

    if has_review_debt_loop or case_quality.kind == "review_overdue":
        cadence = case_quality.cadence_days or thesis.review_cadence_days or 30
        days_old = case_quality.days_old or 0
        return _WorkflowState(
            kind="review_due",
            label="Review due",
            priority=5,
            reason=f"This case is {days_old} days old and outside its {cadence}-day review cadence.",
            cta_label="Refresh thesis",
            cta_href=f"/dashboard/positions/{ticker}?tab=decisions",
        )

    return _WorkflowState(
        kind="calm",
        label="Calm",
        priority=6,
        reason="Nothing urgent is pending right now.",
        cta_label="Open position",
        cta_href=f"/dashboard/positions/{ticker}",
    )


def _to_holding_response(context: _HoldingContext) -> DashboardCommandCenterHoldingResponse:
    top_loop = context.loops[0] if context.loops else None
    supporting = context.supporting
    return DashboardCommandCenterHoldingResponse(
        holding=context.holding,
        thesis_id=context.thesis.id if context.thesis else None,
        workflow_state=context.workflow.kind,
        workflow_label=context.workflow.label,
        workflow_reason=context.workflow.reason,
        primary_cta_label=context.workflow.cta_label,
        primary_cta_href=context.workflow.cta_href,
        pulse_status=context.pulse.pulse_status if context.pulse else None,
        pulse_basis=context.pulse.pulse_basis if context.pulse else None,
        assumption_label=context.pulse.assumption_label if context.pulse else (supporting.assumption_label if supporting else None),
        case_quality=context.case_quality_kind,
        days_since_thesis_update=context.days_since_thesis_update,
        latest_event_summary=context.pulse.latest_event_summary if context.pulse else None,
        supporting_title=supporting.title if supporting else None,
        supporting_summary=(supporting.ai_analysis or supporting.evidence_summary or supporting.summary) if supporting else None,
        supporting_created_at=supporting.created_at if supporting else None,
        open_loop_count=len(context.loops),
        open_loop_title=getattr(top_loop, "title", None),
        open_loop_detail=getattr(top_loop, "detail", None),
    )


def _section(
    *,
    kind: str,
    title: str,
    empty_copy: str,
    contexts: list[_HoldingContext],
) -> DashboardCommandCenterSectionResponse:
    return DashboardCommandCenterSectionResponse(
        kind=kind,
        title=title,
        count=len(contexts),
        empty_copy=empty_copy,
        items=[_to_holding_response(context) for context in contexts[:COMMAND_CENTER_MAX_ITEMS]],
    )


async def _load_current_theses(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holding_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Thesis]:
    if not holding_ids:
        return {}
    result = await db.execute(
        select(Thesis)
        .where(
            Thesis.user_id == user_id,
            Thesis.holding_id.in_(holding_ids),
            Thesis.status.in_(ACTIVE_THESIS_STATUSES),
        )
        .order_by(Thesis.created_at.desc())
    )
    theses_by_holding: dict[uuid.UUID, Thesis] = {}
    for thesis in result.scalars().all():
        theses_by_holding.setdefault(thesis.holding_id, thesis)
    return theses_by_holding


async def _load_latest_decompositions(
    db: AsyncSession,
    *,
    thesis_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ThesisDecomposition]:
    if not thesis_ids:
        return {}
    result = await db.execute(
        select(ThesisDecomposition)
        .where(ThesisDecomposition.thesis_id.in_(thesis_ids))
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
        .order_by(ThesisDecomposition.version.desc())
    )
    latest: dict[uuid.UUID, ThesisDecomposition] = {}
    for decomposition in result.scalars().all():
        latest.setdefault(decomposition.thesis_id, decomposition)
    return latest


async def _load_drafts(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[uuid.UUID, OnboardingDraft]:
    result = await db.execute(
        select(OnboardingDraft)
        .where(OnboardingDraft.user_id == user_id)
        .order_by(OnboardingDraft.updated_at.desc(), OnboardingDraft.created_at.desc())
    )
    latest: dict[uuid.UUID, OnboardingDraft] = {}
    for draft in result.scalars().all():
        latest.setdefault(draft.holding_id, draft)
    return latest


async def _load_supporting_by_holding(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    holdings: list[Holding],
    theses_by_holding: dict[uuid.UUID, Thesis],
) -> dict[uuid.UUID, SupportingItem]:
    if not holdings:
        return {}
    holding_ids = [holding.id for holding in holdings]
    thesis_ids = [thesis.id for thesis in theses_by_holding.values()]
    if not thesis_ids:
        return {}

    now = datetime.now(timezone.utc)
    events = await load_supporting_events_for_holdings(
        db,
        holding_ids=holding_ids,
        thesis_ids=thesis_ids,
        period_start=now - timedelta(days=7),
        period_end=now,
    )
    if not events:
        return {}

    signal_ids = {event.signal_id for event in events if event.signal_id is not None}
    label_by_event: dict[uuid.UUID, str | None] = {}
    if signal_ids:
        signal_rows = await db.execute(
            select(ThesisSignal).where(ThesisSignal.id.in_(signal_ids))
        )
        label_by_signal = {
            signal.id: signal.signal_label
            for signal in signal_rows.scalars().all()
            if signal.signal_label
        }
        label_by_event = {
            event.id: label_by_signal.get(event.signal_id)
            for event in events
            if event.signal_id in label_by_signal
        }

    curated = curate_supporting_items(
        events,
        ticker_by_holding={holding.id: holding.ticker for holding in holdings},
        label_by_event=label_by_event,
        max_items=max(len(holdings), COMMAND_CENTER_MAX_ITEMS),
        max_per_holding=1,
    )
    return {item.holding_id: item for item in curated}


async def build_dashboard_command_center(
    db: AsyncSession,
    *,
    user: User,
) -> DashboardCommandCenterResponse:
    now = datetime.now(timezone.utc)
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user.id).order_by(Holding.current_value.desc().nulls_last(), Holding.ticker.asc())
    )
    raw_holdings = list(holdings_result.scalars().all())
    display = await get_display_currency_context(user)
    holdings = serialize_holdings(raw_holdings, display)
    holdings_by_id = {holding.id: holding for holding in holdings}
    holding_ids = [holding.id for holding in raw_holdings]

    theses_by_holding = await _load_current_theses(db, user_id=user.id, holding_ids=holding_ids)
    latest_decompositions = await _load_latest_decompositions(
        db,
        thesis_ids=[thesis.id for thesis in theses_by_holding.values()],
    )
    drafts_by_holding = await _load_drafts(db, user_id=user.id)
    onboarding_state = (
        await db.execute(
            select(OnboardingState).where(OnboardingState.user_id == user.id)
        )
    ).scalar_one_or_none()
    pulses, _next_digest = await compute_portfolio_pulse(user.id, db)
    pulses_by_holding = {pulse.holding_id: pulse for pulse in pulses}
    open_loops = await list_open_loops(db, user=user, now=now)
    loops_by_holding: dict[uuid.UUID, list] = {}
    for loop in open_loops:
        loops_by_holding.setdefault(loop.holding_id, []).append(loop)
    supporting_by_holding = await _load_supporting_by_holding(
        db,
        user_id=user.id,
        holdings=raw_holdings,
        theses_by_holding=theses_by_holding,
    )

    contexts: list[_HoldingContext] = []
    for raw_holding in raw_holdings:
        holding = holdings_by_id[raw_holding.id]
        thesis = theses_by_holding.get(raw_holding.id)
        pulse = pulses_by_holding.get(raw_holding.id)
        case_quality = classify_case_quality(thesis, now=now)
        draft = drafts_by_holding.get(raw_holding.id)
        loops = loops_by_holding.get(raw_holding.id, [])
        decomposition = latest_decompositions.get(thesis.id) if thesis else None
        has_pending_signal_confirmation = _pending_signal_confirmation(decomposition)
        workflow = _build_workflow_state(
            holding=holding,
            thesis=thesis,
            pulse=pulse,
            case_quality=case_quality,
            draft=draft,
            has_pending_signal_confirmation=has_pending_signal_confirmation,
            loops=loops,
        )
        contexts.append(
            _HoldingContext(
                holding=holding,
                thesis=thesis,
                pulse=pulse,
                case_quality_kind=case_quality.kind,
                case_quality_rank=case_quality.rank,
                days_since_thesis_update=case_quality.days_old,
                draft=draft,
                has_pending_signal_confirmation=has_pending_signal_confirmation,
                supporting=supporting_by_holding.get(raw_holding.id),
                loops=loops,
                workflow=workflow,
            )
        )

    contexts.sort(key=_sort_key)

    needs_review = [
        context for context in contexts
        if context.workflow.kind in {"decision_needed", "pressure_building", "review_due"}
    ]
    held_up = sorted(
        [context for context in contexts if context.supporting is not None],
        key=lambda context: context.supporting.created_at if context.supporting else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    unclear_theses = [
        context for context in contexts
        if context.workflow.kind in {"no_thesis", "draft_ready", "signals_unconfirmed"}
        or context.case_quality_kind in {"weak", "workable"}
    ]
    decision_debt = sorted(
        [context for context in contexts if context.loops],
        key=lambda context: (-len(context.loops), context.workflow.priority, -_holding_value(context.holding)),
    )

    return DashboardCommandCenterResponse(
        investor_profile=onboarding_state.investor_profile if onboarding_state else None,
        summary=DashboardCommandCenterSummaryResponse(
            needs_review_count=len(needs_review),
            held_up_count=len(held_up),
            unclear_theses_count=len(unclear_theses),
            decision_debt_count=len(decision_debt),
        ),
        sections=[
            _section(
                kind="needs_review",
                title="Needs review",
                empty_copy="Nothing urgent needs a call right now.",
                contexts=needs_review,
            ),
            _section(
                kind="held_up",
                title="Held up",
                empty_copy="No fresh supporting evidence surfaced this week.",
                contexts=held_up,
            ),
            _section(
                kind="unclear_theses",
                title="Unclear theses",
                empty_copy="Every live position has at least a workable written case.",
                contexts=unclear_theses,
            ),
            _section(
                kind="decision_debt",
                title="Decision debt",
                empty_copy="No unresolved loops are piling up right now.",
                contexts=decision_debt,
            ),
        ],
    )
