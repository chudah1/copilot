import logging
import re
from dataclasses import dataclass
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
from app.services.conviction_log import (
    FLOOR_APPLIED,
    SIGNAL_CONFIRMED,
    SIGNAL_REMOVED,
    SIGNALS_GENERATED,
    append_log_entry,
)
from app.services.monitoring import DEFAULT_PRICE_THRESHOLD_PCT
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
    "news_topic",
    "transcript_topic",
}

# Monitorability floor: the baseline that guarantees *every* thesis — however
# vague or hard to parse — ends up with at least one active monitorable signal,
# so monitoring always has something to fire on. We reuse the product's standard
# price-move sensitivity (DEFAULT_PRICE_THRESHOLD_PCT) rather than a coarser
# value: monitoring already falls back to that threshold when interpretation is
# empty, so matching it avoids regressing sensitivity for floored theses while
# adding a real, tracked signal + claim (which unlocks news/earnings matching).
# Noise-filter cooldowns keep it from spamming.
FLOOR_PRICE_MOVE_THRESHOLD = DEFAULT_PRICE_THRESHOLD_PCT
FLOOR_SIGNAL_SOURCE = "floor"
SUPPORTED_NUMERIC_SIGNAL_METRICS = {"revenue_growth_yoy", "earnings_growth_yoy"}

_PROXY_REVIEW_KEYWORDS = re.compile(r"\b(margin|cost|expense|overhead|dilution|burn|profitability)\b", re.I)
_ACQUISITION_INTEGRATION_KEYWORDS = re.compile(
    r"\b(acquisition|acquire|acquired|deal|integration|integrate|merger|overhead drag|cost drag)\b",
    re.I,
)
_TEXT_THRESHOLD_HINTS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bdouble[ -]?digits?\b", re.I), 10.0),
    (re.compile(r"\blow single[ -]?digits?\b", re.I), 5.0),
    (re.compile(r"\bmid single[ -]?digits?\b", re.I), 6.0),
    (re.compile(r"\bhigh single[ -]?digits?\b", re.I), 8.0),
]

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
    normalized_signal_config: dict[str, Any] | None = None,
) -> bool:
    config = normalized_signal_config or {}
    signal_type = signal_data.get("signal_type")
    confidence = signal_data.get("confidence") or 0.0
    relation_type = str(entity_data.get("relation_type") or "").strip()
    entity_type = entity_data.get("entity_type")
    entity_ticker = str(entity_data.get("entity_ticker") or "").strip().upper()
    entity_name = str(entity_data.get("entity_name") or "").strip()
    holding_name = str(holding.name or "").strip()

    def _canonical_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    held_company_match = (
        entity_type == "held_company"
        and (
            entity_ticker == holding.ticker.upper()
            or (_canonical_name(entity_name) and _canonical_name(entity_name) == _canonical_name(holding_name))
        )
    )
    explicit_threat_watch = (
        signal_type == "news_topic"
        and relation_type == "threatened_by"
        and confidence >= 0.85
        and bool(config.get("watch_for") or config.get("topic"))
    )
    explicit_integration_watch = (
        signal_type == "news_topic"
        and relation_type == "validated_by"
        and confidence >= 0.8
        and bool(config.get("integration_watch"))
        and bool(config.get("watch_for") or config.get("topic"))
    )
    explicit_transcript_watch = (
        signal_type == "transcript_topic"
        and held_company_match
        and relation_type == "validated_by"
        and confidence >= 0.8
        and bool(config.get("watch_for") or config.get("topic"))
    )

    return (
        (held_company_match or explicit_threat_watch or explicit_integration_watch or explicit_transcript_watch)
        and signal_type in APPROVED_DIRECT_SIGNAL_TYPES
        and confidence >= 0.8
        and (
            explicit_threat_watch
            or explicit_integration_watch
            or explicit_transcript_watch
            or not signal_data.get("confirmation_required", True)
        )
        and not bool(config.get("proxy_review_required"))
    )


def _build_companion_qualitative_signal(
    *,
    entity_data: dict,
    signal_data: dict,
    claim_text: str | None,
) -> dict[str, Any] | None:
    entity_type = entity_data.get("entity_type")
    relation_type = str(entity_data.get("relation_type") or "").strip()
    if entity_type == "held_company" or relation_type != "validated_by":
        return None

    signal_type = signal_data.get("signal_type")
    if signal_type not in {"revenue_growth", "earnings_growth"}:
        return None

    entity_name = str(entity_data.get("entity_name") or "").strip()
    context_parts = [
        entity_name,
        str(signal_data.get("signal_label") or "").strip(),
        str(signal_data.get("rationale") or "").strip(),
        str(claim_text or "").strip(),
    ]
    context = " ".join(part for part in context_parts if part)
    lowered = context.lower()
    if not _ACQUISITION_INTEGRATION_KEYWORDS.search(context):
        return None

    confidence = signal_data.get("confidence") or entity_data.get("confidence") or 0.0
    if confidence < 0.8:
        return None

    subject = entity_name or "the acquisition or integration"
    if signal_type == "revenue_growth" and any(
        token in lowered for token in ("revenue", "contribution", "new revenue", "new line", "traction")
    ):
        watch_for = f"{subject} adds a clear new revenue line"
        return {
            "signal_type": "news_topic",
            "signal_label": f"{subject} integration revenue traction",
            "signal_config_json": {
                "topic": watch_for,
                "watch_for": watch_for,
                "direction": "supports",
                "integration_watch": True,
            },
            "rationale": signal_data.get("rationale") or f"{subject} should contribute visible new revenue traction.",
            "confidence": confidence,
            "confirmation_required": False,
        }

    if signal_type == "earnings_growth" and any(
        token in lowered for token in ("cost", "overhead", "drag", "dilution", "margin", "expense")
    ):
        watch_for = f"{subject} starts reading like overhead drag"
        return {
            "signal_type": "news_topic",
            "signal_label": f"{subject} integration overhead drag",
            "signal_config_json": {
                "topic": watch_for,
                "watch_for": watch_for,
                "direction": "threatens",
                "integration_watch": True,
            },
            "rationale": signal_data.get("rationale") or f"{subject} should not become overhead drag without clear payoff.",
            "confidence": confidence,
            "confirmation_required": False,
        }

    return None


def _watch_hint_from_signal(signal: ThesisSignal, *, override_claim_id: str | None = None) -> dict | None:
    config = signal.signal_config_json or {}
    # Only use the explicit claim id passed from the enclosing persistence loop.
    # Reaching through signal.entity here can trigger async lazy loading.
    claim_id = override_claim_id
    signal_id = str(signal.id)

    if signal.signal_type == "price_move":
        threshold = to_float(config.get("threshold_pct")) or 5.0
        return {
            "kind": "price_move_pct",
            "threshold": threshold,
            "rationale": signal.rationale or "Prompt a review when price moves sharply.",
            "signal_id": signal_id,
            "claim_id": claim_id,
        }
    if signal.signal_type == "revenue_growth":
        threshold = to_float(config.get("threshold")) if isinstance(config, dict) else None
        if threshold is None and isinstance(config, dict):
            threshold_pct = to_float(config.get("threshold_pct"))
            if threshold_pct is not None:
                threshold = threshold_pct / 100.0
        raw_op = config.get("operator", ">=") if isinstance(config, dict) else ">="
        operator = raw_op if raw_op in {">=", "<=", ">", "<", "=="} else ">="
        metric_name = config.get("metric") if isinstance(config, dict) and isinstance(config.get("metric"), str) else "revenue_growth_yoy"
        return {
            "kind": "metric_threshold",
            "metric": metric_name,
            "label": "Revenue Growth (YoY)",
            "unit": "pct",
            "operator": operator,
            "threshold": threshold if threshold is not None else 0.0,
            "rationale": signal.rationale or "Revenue growth should stay healthy.",
            "signal_id": signal_id,
            "claim_id": claim_id,
        }
    if signal.signal_type == "earnings_growth":
        threshold = to_float(config.get("threshold")) if isinstance(config, dict) else None
        if threshold is None and isinstance(config, dict):
            threshold_pct = to_float(config.get("threshold_pct"))
            if threshold_pct is not None:
                threshold = threshold_pct / 100.0
        raw_op = config.get("operator", ">=") if isinstance(config, dict) else ">="
        operator = raw_op if raw_op in {">=", "<=", ">", "<", "=="} else ">="
        metric_name = config.get("metric") if isinstance(config, dict) and isinstance(config.get("metric"), str) else "earnings_growth_yoy"
        return {
            "kind": "metric_threshold",
            "metric": metric_name,
            "label": "Earnings Growth (YoY)",
            "unit": "pct",
            "operator": operator,
            "threshold": threshold if threshold is not None else 0.0,
            "rationale": signal.rationale or "Earnings growth should remain healthy.",
            "signal_id": signal_id,
            "claim_id": claim_id,
        }
    if signal.signal_type in {"news_topic", "transcript_topic", "news_watch"}:
        watch_for = ""
        direction = "threatens"
        label = signal.signal_label or None
        if signal.signal_type == "news_watch":
            watch_for = str(config.get("watch_for") or "").strip()
            raw_direction = str(config.get("direction") or "threatens").strip().lower()
            direction = raw_direction if raw_direction in {"threatens", "supports"} else "threatens"
        else:
            watch_for = str(
                config.get("watch_for")
                or config.get("topic")
                or signal.signal_label
                or signal.rationale
                or ""
            ).strip()
            raw_direction = str(config.get("direction") or "supports").strip().lower()
            direction = raw_direction if raw_direction in {"threatens", "supports"} else "supports"
        if not watch_for:
            return None
        return {
            "kind": "news_watch",
            "watch_for": watch_for,
            "direction": direction,
            "label": label,
            "rationale": signal.rationale or watch_for,
            "signal_id": signal_id,
            "claim_id": claim_id,
        }
    return None


def _extract_threshold_pct_from_text(*parts: str | None) -> float | None:
    for part in parts:
        if not part:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)\s*%", part)
        if match:
            value = to_float(match.group(1))
            if value is not None:
                return value
        for pattern, threshold in _TEXT_THRESHOLD_HINTS:
            if pattern.search(part):
                return threshold
    return None


def _normalize_signal_config_json(
    *,
    signal_type: str,
    signal_label: str | None,
    claim_text: str | None,
    rationale: str | None,
    raw_config: dict[str, Any] | None,
) -> dict[str, Any]:
    config = dict(raw_config or {})

    if signal_type == "price_move":
        config["threshold_pct"] = to_float(config.get("threshold_pct")) or FLOOR_PRICE_MOVE_THRESHOLD
        return config

    if signal_type in {"news_topic", "transcript_topic"}:
        topic = str(config.get("topic") or signal_label or claim_text or "").strip()
        if topic:
            config["topic"] = topic
            config.setdefault("watch_for", topic)
        return config

    if signal_type not in {"revenue_growth", "earnings_growth"}:
        return config

    default_metric = "revenue_growth_yoy" if signal_type == "revenue_growth" else "earnings_growth_yoy"
    metric_name = config.get("metric") if isinstance(config.get("metric"), str) else None
    if metric_name not in SUPPORTED_NUMERIC_SIGNAL_METRICS:
        config["metric"] = default_metric
        if signal_label or claim_text:
            config["proxy_for"] = signal_label or claim_text
        if metric_name:
            config["proxy_source_metric"] = metric_name

    context_blob = " ".join(part for part in (signal_label, claim_text, rationale, config.get("proxy_for")) if part)
    if (
        signal_type == "earnings_growth"
        and (
            config.get("proxy_source_metric") in {"gross_margin", "operating_margin"}
            or _PROXY_REVIEW_KEYWORDS.search(context_blob)
        )
    ):
        config["proxy_review_required"] = True

    if config.get("operator") not in {">=", "<=", ">", "<", "=="}:
        config["operator"] = ">="

    if to_float(config.get("threshold")) is None and to_float(config.get("threshold_pct")) is None:
        threshold_pct = _extract_threshold_pct_from_text(signal_label, claim_text, rationale)
        config["threshold_pct"] = threshold_pct if threshold_pct is not None else 0.0

    return config


def _sync_interpretation_cache(
    thesis: Thesis,
    *,
    reason_type: str | None,
    monitorability: str | None,
    labels: list[str],
    active_signals: list[ThesisSignal],
    signal_claim_map: dict[str, str] | None = None,
) -> None:
    if not active_signals:
        thesis.interpretation = None
        return

    watch_hints: list[dict] = []
    seen_metric_hints: set[tuple] = set()
    for signal in active_signals:
        override = signal_claim_map.get(str(signal.id)) if signal_claim_map else None
        hint = _watch_hint_from_signal(signal, override_claim_id=override)
        if hint is None:
            continue
        if hint.get("kind") == "metric_threshold":
            dedup_key = (hint.get("metric"), hint.get("operator"), hint.get("threshold"))
            if dedup_key in seen_metric_hints:
                continue
            seen_metric_hints.add(dedup_key)
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


async def _load_active_signals_with_claims(
    db: AsyncSession, decomposition_id
) -> list[tuple[ThesisSignal, str]]:
    """Return (signal, claim_id) for every active signal under a decomposition.

    Uses an explicit join rather than walking ORM relationships — reaching
    through lazy relationships in async SQLAlchemy can trigger implicit IO and
    raise. Callers rely on this being safe at any point in a transaction.
    """
    rows = await db.execute(
        select(ThesisSignal, ThesisClaim.id)
        .join(ThesisEntity, ThesisSignal.entity_id == ThesisEntity.id)
        .join(ThesisClaim, ThesisEntity.claim_id == ThesisClaim.id)
        .where(
            ThesisClaim.decomposition_id == decomposition_id,
            ThesisSignal.active.is_(True),
        )
    )
    return [(sig, str(claim_id)) for sig, claim_id in rows.all()]


async def ensure_signal_floor(
    db: AsyncSession,
    thesis: Thesis,
    holding: Holding,
    decomposition: ThesisDecomposition,
) -> bool:
    """Guarantee the thesis has at least one active monitorable signal.

    No-op (returns False) when the decomposition already has an active signal.
    Otherwise injects a baseline floor — reusing the first existing claim/entity
    or creating one (the raw reason as a claim, the held company as the entity)
    — plus an active coarse price-move signal, then rebuilds the interpretation
    cache so monitoring produces candidates. Returns True when a floor was added.

    Idempotent: a second call sees the floor signal active and no-ops. The caller
    is responsible for committing.
    """
    if await _load_active_signals_with_claims(db, decomposition.id):
        return False

    # Defensive: the floor is the never-fail path, so it must not crash on a
    # missing/odd ticker.
    ticker = (holding.ticker or "").upper()
    ticker_display = holding.ticker or "this holding"

    # Reuse the first existing claim, or create the floor claim.
    claim = (
        await db.execute(
            select(ThesisClaim)
            .where(ThesisClaim.decomposition_id == decomposition.id)
            .order_by(ThesisClaim.position)
            .limit(1)
        )
    ).scalar_one_or_none()
    if claim is None:
        claim = ThesisClaim(
            decomposition_id=decomposition.id,
            claim_text=(thesis.why_own_it or "").strip() or f"Reason for owning {ticker_display}",
            claim_type="overall",
            confidence=0.4,
            position=1,
        )
        db.add(claim)
        await db.flush()

    # Reuse the claim's first NON-REJECTED entity, or create the held-company
    # entity. We never attach an active signal under an entity the user
    # explicitly rejected (user_confirmed is False).
    entity = (
        await db.execute(
            select(ThesisEntity)
            .where(
                ThesisEntity.claim_id == claim.id,
                ThesisEntity.user_confirmed.isnot(False),
            )
            .order_by(ThesisEntity.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if entity is None:
        entity = ThesisEntity(
            claim_id=claim.id,
            entity_name=holding.name or ticker_display,
            entity_ticker=ticker or None,
            entity_type="held_company",
            relation_type="self",
            confidence=0.4,
            confirmation_required=False,
            user_confirmed=True,
        )
        db.add(entity)
        await db.flush()

    floor_signal = ThesisSignal(
        entity_id=entity.id,
        signal_type="price_move",
        signal_label=f"Price moves more than {int(FLOOR_PRICE_MOVE_THRESHOLD)}%",
        signal_config_json={"threshold_pct": FLOOR_PRICE_MOVE_THRESHOLD},
        rationale=(
            "Baseline watch so a vague or hard-to-parse thesis still gets "
            "reviewed when the stock moves sharply."
        ),
        confidence=0.4,
        confirmation_required=False,
        user_confirmed=True,
        active=True,
        raw_extraction_json={"source": FLOOR_SIGNAL_SOURCE},
    )
    db.add(floor_signal)
    await db.flush()

    # Rebuild the interpretation cache from the now-active signals.
    active = await _load_active_signals_with_claims(db, decomposition.id)
    active_signals = [sig for sig, _ in active]
    signal_claim_map = {str(sig.id): claim_id for sig, claim_id in active}
    label_rows = await db.execute(
        select(ThesisClaim.claim_type).where(ThesisClaim.decomposition_id == decomposition.id)
    )
    labels = [lt for (lt,) in label_rows.all() if lt]
    _sync_interpretation_cache(
        thesis,
        reason_type=decomposition.reason_type,
        monitorability=decomposition.monitorability or "low",
        labels=labels,
        active_signals=active_signals,
        signal_claim_map=signal_claim_map,
    )
    return True


async def _persist_floor_decomposition(
    db: AsyncSession,
    thesis: Thesis,
    holding: Holding,
    result,
) -> ThesisDecomposition:
    """Create a minimal, immediately-monitorable decomposition when the AI
    decomposition could not be produced — so the thesis is never left
    unmonitored. Status is ``partially_confirmed`` because the floor signal is
    system-activated (no user review pending), which makes it usable by the
    monitoring pipeline right away.
    """
    decomposition = ThesisDecomposition(
        thesis_id=thesis.id,
        version=await _next_version(db, thesis.id),
        status="partially_confirmed",
        reason_type=None,
        monitorability="low",
        decomposition_confidence=None,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        raw_output_json=result.raw_output,
        retry_count=0,
        last_error=result.failure_reason,
        next_retry_at=None,
    )
    db.add(decomposition)
    await db.flush()
    floored = await ensure_signal_floor(db, thesis, holding, decomposition)
    if floored:
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=thesis.user_id,
            entry_type=FLOOR_APPLIED,
            content="Baseline monitoring applied (we couldn't fully parse this thesis yet).",
            metadata={
                "decomposition_id": str(decomposition.id),
                "failure_reason": result.failure_reason,
            },
        )
    await db.commit()
    return decomposition


CANDIDATE_SIGNAL_SOURCE = "stress_test"


# Signal types a user can confirm from the climb (numeric + qualitative).
CONFIRMABLE_CANDIDATE_SIGNAL_TYPES = {
    "price_move",
    "revenue_growth",
    "earnings_growth",
    "news_watch",
}


def _candidate_signal_config(candidate) -> dict:
    """Build the signal config for a candidate. Numeric watches compare against
    the market feed (price in percent; growth as the fraction the feed uses, e.g.
    0.13 not 13). A news_watch stores its natural-language condition + direction;
    it is evaluated by the AI against news, not a number."""
    if candidate.signal_type == "news_watch":
        return {
            "watch_for": candidate.watch_for,
            "direction": candidate.direction or "threatens",
        }
    if candidate.signal_type == "price_move":
        return {"threshold_pct": float(candidate.threshold_pct)}
    return {"threshold": float(candidate.threshold_pct) / 100.0, "operator": candidate.operator or ">="}


def _signal_config_key(config: dict | None) -> tuple:
    """Hashable identity for an active signal, used to dedupe candidate inserts."""
    return tuple(sorted((config or {}).items()))


async def apply_candidate_signals_to_thesis(
    db: AsyncSession,
    thesis: Thesis,
    holding: Holding,
    candidates,
) -> int:
    """Persist user-confirmed stress-test candidate signals as ACTIVE monitorable
    signals on the thesis, and rebuild the interpretation cache. Returns the
    count added. Closes the climb loop: a vague thesis -> stress-test -> chosen
    measurable watches -> live monitoring.

    Each candidate must expose .signal_type / .label / .threshold_pct /
    .rationale / .operator. Unknown signal types are ignored. Caller commits.
    """
    valid = [c for c in candidates if c.signal_type in CONFIRMABLE_CANDIDATE_SIGNAL_TYPES]
    if not valid:
        return 0

    # Attach only to the decomposition the monitoring pipeline already treats as
    # live (same filter/order as load_active_decomposition). This avoids
    # shadowing a confirmed decomposition with a higher-version draft and avoids
    # resurrecting a rejected one. If none is active, create a fresh decomposition
    # for the user-confirmed watches rather than mutating an existing one.
    decomposition = (
        await db.execute(
            select(ThesisDecomposition)
            .where(
                ThesisDecomposition.thesis_id == thesis.id,
                ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
            )
            .order_by(ThesisDecomposition.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if decomposition is None:
        decomposition = ThesisDecomposition(
            thesis_id=thesis.id,
            version=await _next_version(db, thesis.id),
            status="partially_confirmed",
            monitorability="medium",
        )
        db.add(decomposition)
        await db.flush()

    ticker = (holding.ticker or "").upper()
    ticker_display = holding.ticker or "this holding"

    claim = (
        await db.execute(
            select(ThesisClaim)
            .where(ThesisClaim.decomposition_id == decomposition.id)
            .order_by(ThesisClaim.position)
            .limit(1)
        )
    ).scalar_one_or_none()
    if claim is None:
        claim = ThesisClaim(
            decomposition_id=decomposition.id,
            claim_text=(thesis.why_own_it or "").strip() or f"Reason for owning {ticker_display}",
            claim_type="overall",
            confidence=0.5,
            position=1,
        )
        db.add(claim)
        await db.flush()

    entity = (
        await db.execute(
            select(ThesisEntity)
            .where(
                ThesisEntity.claim_id == claim.id,
                ThesisEntity.user_confirmed.isnot(False),
            )
            .order_by(ThesisEntity.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if entity is None:
        entity = ThesisEntity(
            claim_id=claim.id,
            entity_name=holding.name or ticker_display,
            entity_ticker=ticker or None,
            entity_type="held_company",
            relation_type="self",
            confidence=0.5,
            confirmation_required=False,
            user_confirmed=True,
        )
        db.add(entity)
        await db.flush()

    # Idempotency: don't re-add a watch the thesis already has active (a
    # double-clicked confirm must not create duplicate signals).
    existing = await _load_active_signals_with_claims(db, decomposition.id)
    existing_keys = {
        (sig.signal_type, _signal_config_key(sig.signal_config_json)) for sig, _ in existing
    }
    added_signals: list[ThesisSignal] = []
    for c in valid:
        config = _candidate_signal_config(c)
        key = (c.signal_type, _signal_config_key(config))
        if key in existing_keys:
            continue
        existing_keys.add(key)
        signal = ThesisSignal(
            entity_id=entity.id,
            signal_type=c.signal_type,
            signal_label=c.label,
            signal_config_json=config,
            rationale=(c.rationale or None),
            confidence=0.6,
            confirmation_required=False,
            user_confirmed=True,
            active=True,
            raw_extraction_json={"source": CANDIDATE_SIGNAL_SOURCE},
        )
        db.add(signal)
        added_signals.append(signal)

    if not added_signals:
        return 0
    await db.flush()

    for signal in added_signals:
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=thesis.user_id,
            entry_type=SIGNAL_CONFIRMED,
            content=f"Added from grounding: {signal.signal_label or signal.signal_type}",
            signal_id=signal.id,
            claim_id=claim.id,
        )

    active = await _load_active_signals_with_claims(db, decomposition.id)
    active_signals = [sig for sig, _ in active]
    signal_claim_map = {str(sig.id): claim_id for sig, claim_id in active}
    label_rows = await db.execute(
        select(ThesisClaim.claim_type).where(ThesisClaim.decomposition_id == decomposition.id)
    )
    labels = [lt for (lt,) in label_rows.all() if lt]
    _sync_interpretation_cache(
        thesis,
        reason_type=decomposition.reason_type,
        monitorability=decomposition.monitorability or "medium",
        labels=labels,
        active_signals=active_signals,
        signal_claim_map=signal_claim_map,
    )
    return len(added_signals)


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
    signal_claim_map: dict[str, str] = {}  # signal_id -> claim_id for freshly built signals

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

            signal_payloads = list(entity_data.get("signals", []))
            existing_signal_types = {
                (
                    str(sig.get("signal_type") or "").strip(),
                    str(sig.get("signal_label") or "").strip().lower(),
                )
                for sig in signal_payloads
            }
            for signal_data in list(signal_payloads):
                companion_signal = _build_companion_qualitative_signal(
                    entity_data=entity_data,
                    signal_data=signal_data,
                    claim_text=claim.claim_text,
                )
                if companion_signal:
                    companion_key = (
                        str(companion_signal.get("signal_type") or "").strip(),
                        str(companion_signal.get("signal_label") or "").strip().lower(),
                    )
                    if companion_key not in existing_signal_types:
                        signal_payloads.append(companion_signal)
                        existing_signal_types.add(companion_key)

            for signal_data in signal_payloads:
                normalized_signal_config = _normalize_signal_config_json(
                    signal_type=signal_data["signal_type"],
                    signal_label=signal_data.get("signal_label"),
                    claim_text=claim.claim_text,
                    rationale=signal_data.get("rationale"),
                    raw_config=signal_data.get("signal_config_json") or {},
                )
                if signal_data["signal_type"] in {"news_topic", "transcript_topic"}:
                    relation_type = str(entity_data.get("relation_type") or "").strip()
                    inferred_direction = (
                        "threatens" if relation_type == "threatened_by" else "supports"
                    )
                    normalized_signal_config.setdefault("direction", inferred_direction)
                    normalized_signal_config.setdefault(
                        "watch_for",
                        str(
                            normalized_signal_config.get("topic")
                            or signal_data.get("signal_label")
                            or signal_data.get("rationale")
                            or claim.claim_text
                            or ""
                        ).strip(),
                    )
                auto_activate = _signal_is_direct_and_auto_activatable(
                    holding,
                    entity_data,
                    signal_data,
                    normalized_signal_config,
                )
                signal_confirmation_required = signal_data.get("confirmation_required", True) or bool(
                    normalized_signal_config.get("proxy_review_required")
                )
                signal = ThesisSignal(
                    entity_id=entity.id,
                    signal_type=signal_data["signal_type"],
                    signal_label=signal_data.get("signal_label"),
                    signal_config_json=normalized_signal_config,
                    rationale=signal_data.get("rationale"),
                    confidence=signal_data.get("confidence"),
                    confirmation_required=signal_confirmation_required,
                    user_confirmed=True if auto_activate else None,
                    active=auto_activate,
                    raw_extraction_json=signal_data.get("raw_extraction_json"),
                )
                db.add(signal)
                if auto_activate:
                    active_signals.append(signal)
                    signal_claim_map[str(signal.id)] = str(claim.id)

    await db.flush()
    _sync_interpretation_cache(
        thesis,
        reason_type=normalized.get("reason_type"),
        monitorability=normalized.get("monitorability"),
        labels=interpretation_labels,
        active_signals=active_signals,
        signal_claim_map=signal_claim_map,
    )

    # Conviction log: signals generated
    total_claims = len(normalized.get("claims", []))
    total_signals = sum(
        len(sig_list)
        for c in normalized.get("claims", [])
        for e in c.get("entities", [])
        for sig_list in [e.get("signals", [])]
    )
    total_entities = sum(
        len(c.get("entities", []))
        for c in normalized.get("claims", [])
    )
    append_log_entry(
        db,
        thesis_id=thesis.id,
        holding_id=holding.id,
        user_id=thesis.user_id,
        entry_type=SIGNALS_GENERATED,
        content=f"{total_signals} signals across {total_entities} entities",
        metadata={
            "decomposition_id": str(decomposition.id),
            "claims": total_claims,
            "entities": total_entities,
            "signals": total_signals,
            "auto_activated": len(active_signals),
        },
    )

    # NOTE: no floor here. A successful decomposition whose signals all need
    # user confirmation intentionally stays unmonitored (interpretation=None)
    # until the user confirms — that is the product's review flow. The floor is
    # applied only at finalization points: decomposition failure (see
    # generate_decomposition_for_thesis) and confirmation that leaves zero
    # active signals (see confirm_decomposition_for_thesis).

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

    # One automatic retry for transient failures (network hiccup, rate limit, etc.)
    if result.retryable:
        logger.info("Decomposition failed (retryable) for thesis %s — retrying once", thesis.id)
        result = await gateway.run(request)
        if result.success and result.normalized_output is not None:
            decomposition = await _persist_successful_decomposition(db, thesis, holding, result)
            return PersistedDecompositionResult(status="draft", message=None, decomposition=decomposition)

    # The AI decomposition is unusable — but never leave the thesis unmonitored.
    # Persist a baseline floor so monitoring still fires, and surface guidance to
    # sharpen it. (There is no background retry job, so a transient failure would
    # otherwise leave the thesis permanently dead.)
    logger.warning(
        "Decomposition unavailable for thesis %s (%s) — applying monitorability floor",
        thesis.id,
        result.failure_reason,
    )
    decomposition = await _persist_floor_decomposition(db, thesis, holding, result)
    if result.failure_reason and "confidence too low" in result.failure_reason.lower():
        message = (
            "We saved your thesis and set up baseline monitoring. To watch it more precisely, "
            "add concrete metrics — e.g. 'Revenue growth above 15% YoY', 'Gross margin holds above 60%', "
            "or 'Market share stays above 40%'."
        )
    else:
        message = "We saved your thesis and set up baseline monitoring. You can refine what we watch anytime."
    return PersistedDecompositionResult(status="draft", message=message, decomposition=decomposition)


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
    # Carry claim_ids into the rebuilt hints so event->claim linkage survives a
    # confirm cycle (the loaded tree is eager, so walking it is safe here).
    signal_claim_map = {
        str(signal.id): str(claim.id)
        for claim in decomposition.claims
        for entity in claim.entities
        for signal in entity.signals
        if signal.active
    }
    _sync_interpretation_cache(
        thesis,
        reason_type=decomposition.reason_type,
        monitorability=decomposition.monitorability,
        labels=labels,
        active_signals=active_signals,
        signal_claim_map=signal_claim_map,
    )

    # Conviction log: signal confirmed / removed
    for signal_update in signal_confirmations:
        signal = signals_by_id.get(signal_update["id"])
        if signal is None:
            continue
        if signal.user_confirmed is True:
            append_log_entry(
                db,
                thesis_id=thesis.id,
                holding_id=holding.id,
                user_id=thesis.user_id,
                entry_type=SIGNAL_CONFIRMED,
                content=f"Confirmed: {signal.signal_label or signal.signal_type}",
                signal_id=signal.id,
            )
        elif signal.user_confirmed is False:
            append_log_entry(
                db,
                thesis_id=thesis.id,
                holding_id=holding.id,
                user_id=thesis.user_id,
                entry_type=SIGNAL_REMOVED,
                content=f"Removed: {signal.signal_label or signal.signal_type}",
                signal_id=signal.id,
            )

    # No floor here. If a user reviews the proposed signals and deliberately
    # rejects all of them, that is an explicit choice to stop monitoring — we
    # respect it (interpretation clears). The floor is for *inability* to produce
    # signals (decomposition failure), not *unwillingness* to keep them.

    await db.commit()
    await db.refresh(decomposition)
    return decomposition
