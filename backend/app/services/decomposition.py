import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.holding import Holding
from app.models.thesis import Thesis
from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal
from app.services.reasoning.gateway import ThesisReasoningGateway
from app.services.reasoning.normalizers import normalize_decomposition_output, to_float
from app.services.reasoning.providers import (
    AnthropicReasoningProvider,
    GeminiReasoningProvider,
    OpenAIReasoningProvider,
)
from app.services.reasoning.types import ReasoningRequest, ReasoningResult, ReasoningTaskType
from app.services.reasoning.validators import validate_decomposition_output

logger = logging.getLogger(__name__)

APPROVED_DIRECT_SIGNAL_TYPES = {
    "price_move",
    "revenue_growth",
    "earnings_growth",
    "guidance_change",
    "earnings_surprise",
    "dividend_change",
}

_gateway: ThesisReasoningGateway | None = None


@dataclass
class PersistedDecompositionResult:
    status: str
    message: str | None
    decomposition: ThesisDecomposition | None


def get_reasoning_gateway() -> ThesisReasoningGateway:
    global _gateway
    if _gateway is None:
        _gateway = ThesisReasoningGateway()
    return _gateway


async def debug_compare_decomposition_providers(payload: dict[str, Any]) -> dict[str, Any]:
    request = ReasoningRequest(
        task_type=ReasoningTaskType.DECOMPOSE_THESIS,
        thesis_id="debug",
        user_id="debug",
        payload=payload,
    )
    providers = [
        OpenAIReasoningProvider(),
        AnthropicReasoningProvider(),
        GeminiReasoningProvider(),
    ]
    provider_results: list[dict[str, Any]] = []
    original_text = str(payload.get("why_own_it", ""))

    for provider in providers:
        try:
            result = await provider.run(request)
        except Exception as exc:
            logger.exception(
                "Debug provider %s raised an unhandled exception",
                getattr(provider, "name", "<unknown>"),
            )
            result = ReasoningResult(
                success=False,
                status="failed",
                provider=getattr(provider, "name", None),
                model=getattr(provider, "model", None),
                prompt_version=None,
                normalized_output=None,
                raw_output=None,
                confidence=None,
                latency_ms=None,
                failure_reason=str(exc),
                retryable=True,
            )

        normalized_output: dict[str, Any] | None = None
        valid = False
        validation_error: str | None = None

        if result.success and result.raw_output is not None:
            normalized_output = normalize_decomposition_output(result.raw_output)
            valid, validation_error = validate_decomposition_output(
                normalized_output,
                original_text=original_text,
            )

        provider_results.append(
            {
                "provider": provider.name,
                "model": getattr(provider, "model", None),
                "success": result.success,
                "status": result.status,
                "latency_ms": result.latency_ms,
                "failure_reason": result.failure_reason,
                "raw_output": result.raw_output,
                "normalized_output": normalized_output,
                "valid": valid,
                "validation_error": validation_error,
            }
        )

    gateway = ThesisReasoningGateway(providers=providers)
    gateway_result = await gateway.run(request)
    return {
        "providers": provider_results,
        "gateway_result": {
            "success": gateway_result.success,
            "status": gateway_result.status,
            "provider": gateway_result.provider,
            "model": gateway_result.model,
            "confidence": gateway_result.confidence,
            "latency_ms": gateway_result.latency_ms,
            "failure_reason": gateway_result.failure_reason,
            "normalized_output": gateway_result.normalized_output,
        },
    }


def _signal_is_direct_and_auto_activatable(
    holding: Holding,
    entity_data: dict,
    signal_data: dict,
) -> bool:
    entity_ticker = entity_data.get("entity_ticker")
    return (
        entity_ticker == holding.ticker.upper()
        and entity_data.get("entity_type") == "held_company"
        and signal_data.get("signal_type") in APPROVED_DIRECT_SIGNAL_TYPES
        and (signal_data.get("confidence") or 0.0) >= 0.8
        and not signal_data.get("confirmation_required", True)
    )


def _watch_hint_from_signal(signal: ThesisSignal) -> dict | None:
    config = signal.signal_config_json or {}
    if signal.signal_type == "price_move":
        threshold = to_float(config.get("threshold_pct")) or 5.0
        return {
            "kind": "price_move_pct",
            "threshold": threshold,
            "rationale": signal.rationale or "Prompt a review when price moves sharply.",
        }
    if signal.signal_type == "revenue_growth":
        threshold = to_float(config.get("threshold")) if isinstance(config, dict) else None
        raw_op = config.get("operator", ">=") if isinstance(config, dict) else ">="
        operator = raw_op if raw_op in {">=", "<=", ">", "<", "=="} else ">="
        return {
            "kind": "metric_threshold",
            "metric": "revenue_growth_yoy",
            "operator": operator,
            "threshold": threshold if threshold is not None else 0.0,
            "rationale": signal.rationale or "Revenue growth should stay healthy.",
        }
    if signal.signal_type == "earnings_growth":
        threshold = to_float(config.get("threshold")) if isinstance(config, dict) else None
        raw_op = config.get("operator", ">=") if isinstance(config, dict) else ">="
        operator = raw_op if raw_op in {">=", "<=", ">", "<", "=="} else ">="
        return {
            "kind": "metric_threshold",
            "metric": "earnings_growth_yoy",
            "operator": operator,
            "threshold": threshold if threshold is not None else 0.0,
            "rationale": signal.rationale or "Earnings growth should remain healthy.",
        }
    return None


def _sync_interpretation_cache(
    thesis: Thesis,
    *,
    reason_type: str | None,
    monitorability: str | None,
    labels: list[str],
    active_signals: list[ThesisSignal],
) -> None:
    if not active_signals:
        thesis.interpretation = None
        return

    watch_hints: list[dict] = []
    for signal in active_signals:
        hint = _watch_hint_from_signal(signal)
        if hint is not None:
            watch_hints.append(hint)

    thesis.interpretation = {
        "labels": labels[:3] or [reason_type or "user_defined"],
        "monitorability": monitorability or "medium",
        "watch_hints": watch_hints[:3],
        "proxy_signals": [],
        "ambiguity_note": "",
    }


async def _next_version(db: AsyncSession, thesis_id) -> int:
    version_result = await db.execute(
        select(func.max(ThesisDecomposition.version)).where(ThesisDecomposition.thesis_id == thesis_id)
    )
    current_max = version_result.scalar_one_or_none() or 0
    return current_max + 1


async def _persist_pending_decomposition(
    db: AsyncSession,
    thesis: Thesis,
    result,
) -> ThesisDecomposition:
    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=await _next_version(db, thesis.id),
        status=result.status,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        raw_output_json=result.raw_output,
        retry_count=0,
        last_error=result.failure_reason,
        next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=15) if result.retryable else None,
    )
    db.add(decomposition)
    await db.commit()
    return decomposition


async def _persist_successful_decomposition(
    db: AsyncSession,
    thesis: Thesis,
    holding: Holding,
    result,
) -> ThesisDecomposition:
    normalized = result.normalized_output or {}
    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=await _next_version(db, thesis.id),
        status="draft",
        reason_type=normalized.get("reason_type"),
        monitorability=normalized.get("monitorability"),
        decomposition_confidence=normalized.get("decomposition_confidence"),
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        raw_output_json=result.raw_output,
        retry_count=0,
        last_error=None,
        next_retry_at=None,
    )
    db.add(decomposition)
    await db.flush()

    interpretation_labels: list[str] = []
    active_signals: list[ThesisSignal] = []

    for position, claim_data in enumerate(normalized.get("claims", []), start=1):
        if claim_data.get("claim_type") and claim_data["claim_type"] not in interpretation_labels:
            interpretation_labels.append(claim_data["claim_type"])
        claim = ThesisClaim(
            decomposition_id=decomposition.id,
            claim_text=claim_data["claim_text"],
            claim_type=claim_data.get("claim_type"),
            confidence=claim_data.get("confidence"),
            position=claim_data.get("position", position),
            raw_extraction_json=claim_data.get("raw_extraction_json"),
        )
        db.add(claim)
        await db.flush()

        for entity_data in claim_data.get("entities", []):
            entity_confirmed = (
                entity_data.get("entity_ticker") == holding.ticker.upper()
                and entity_data.get("entity_type") == "held_company"
                and not entity_data.get("confirmation_required", True)
            )
            entity = ThesisEntity(
                claim_id=claim.id,
                entity_name=entity_data["entity_name"],
                entity_ticker=entity_data.get("entity_ticker"),
                entity_type=entity_data.get("entity_type"),
                relation_type=entity_data.get("relation_type"),
                rationale=entity_data.get("rationale"),
                confidence=entity_data.get("confidence"),
                confirmation_required=entity_data.get("confirmation_required", True),
                user_confirmed=True if entity_confirmed else None,
                raw_extraction_json=entity_data.get("raw_extraction_json"),
            )
            db.add(entity)
            await db.flush()

            for signal_data in entity_data.get("signals", []):
                auto_activate = _signal_is_direct_and_auto_activatable(holding, entity_data, signal_data)
                signal = ThesisSignal(
                    entity_id=entity.id,
                    signal_type=signal_data["signal_type"],
                    signal_label=signal_data.get("signal_label"),
                    signal_config_json=signal_data.get("signal_config_json") or {},
                    rationale=signal_data.get("rationale"),
                    confidence=signal_data.get("confidence"),
                    confirmation_required=signal_data.get("confirmation_required", True),
                    user_confirmed=True if auto_activate else None,
                    active=auto_activate,
                    raw_extraction_json=signal_data.get("raw_extraction_json"),
                )
                db.add(signal)
                if auto_activate:
                    active_signals.append(signal)

    await db.flush()
    _sync_interpretation_cache(
        thesis,
        reason_type=normalized.get("reason_type"),
        monitorability=normalized.get("monitorability"),
        labels=interpretation_labels,
        active_signals=active_signals,
    )
    await db.commit()
    return decomposition


async def generate_decomposition_for_thesis(
    db: AsyncSession,
    thesis: Thesis,
    holding: Holding,
) -> PersistedDecompositionResult:
    request = ReasoningRequest(
        task_type=ReasoningTaskType.DECOMPOSE_THESIS,
        thesis_id=str(thesis.id),
        user_id=str(thesis.user_id),
        payload={
            "ticker": holding.ticker,
            "name": holding.name,
            "why_own_it": thesis.why_own_it,
            "must_remain_true": thesis.must_remain_true,
            "what_would_change_my_mind": thesis.what_would_change_my_mind,
        },
    )
    gateway = get_reasoning_gateway()
    result = await gateway.run(request)

    if result.success and result.normalized_output is not None:
        decomposition = await _persist_successful_decomposition(db, thesis, holding, result)
        return PersistedDecompositionResult(status="draft", message=None, decomposition=decomposition)

    decomposition = await _persist_pending_decomposition(db, thesis, result)
    status = decomposition.status
    message = "We saved your thesis and are retrying decomposition." if status == "pending" else "We could not decompose this thesis right now."
    logger.warning("Decomposition unavailable for thesis %s: %s", thesis.id, result.failure_reason)
    return PersistedDecompositionResult(status=status, message=message, decomposition=None)


async def confirm_decomposition_for_thesis(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    decomposition_id,
    entity_confirmations: list[dict[str, Any]],
    signal_confirmations: list[dict[str, Any]],
) -> ThesisDecomposition | None:
    result = await db.execute(
        select(ThesisDecomposition)
        .where(
            ThesisDecomposition.id == decomposition_id,
            ThesisDecomposition.thesis_id == thesis.id,
        )
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
    )
    decomposition = result.scalar_one_or_none()
    if decomposition is None:
        return None

    entities_by_id = {
        entity.id: entity
        for claim in decomposition.claims
        for entity in claim.entities
    }
    signals_by_id = {
        signal.id: signal
        for entity in entities_by_id.values()
        for signal in entity.signals
    }

    for entity_update in entity_confirmations:
        entity = entities_by_id.get(entity_update["id"])
        if entity is None:
            continue
        entity.user_confirmed = entity_update["user_confirmed"]
        if entity.user_confirmed is False:
            for signal in entity.signals:
                signal.user_confirmed = False
                signal.active = False

    for signal_update in signal_confirmations:
        signal = signals_by_id.get(signal_update["id"])
        if signal is None:
            continue
        signal.user_confirmed = signal_update["user_confirmed"]
        signal.active = bool(signal_update["active"]) and signal.user_confirmed is True
        if signal.user_confirmed is True:
            signal.entity.user_confirmed = True

    all_confirmation_values: list[bool] = []
    for entity in entities_by_id.values():
        if entity.user_confirmed is not None:
            all_confirmation_values.append(entity.user_confirmed)
        for signal in entity.signals:
            if signal.user_confirmed is not None:
                all_confirmation_values.append(signal.user_confirmed)

    any_true = any(all_confirmation_values)
    any_false = any(value is False for value in all_confirmation_values)

    if all_confirmation_values and not any_true:
        decomposition.status = "rejected"
    elif any_true and any_false:
        decomposition.status = "partially_confirmed"
    elif any_true:
        decomposition.status = "confirmed"
    else:
        decomposition.status = "draft"

    labels: list[str] = []
    for claim in decomposition.claims:
        if claim.claim_type and claim.claim_type not in labels:
            labels.append(claim.claim_type)

    active_signals = [
        signal
        for signal in signals_by_id.values()
        if signal.active
    ]
    _sync_interpretation_cache(
        thesis,
        reason_type=decomposition.reason_type,
        monitorability=decomposition.monitorability,
        labels=labels,
        active_signals=active_signals,
    )

    await db.commit()
    await db.refresh(decomposition)
    return decomposition
