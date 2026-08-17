import re
from typing import Any

from app.services.signal_quality import cap_claim_signals, filter_signal_payloads


VALID_REASON_TYPES = {
    "business_performance",
    "valuation",
    "macro_theme",
    "income",
    "portfolio_role",
    "behavioral",
    "social_proof",
    "constraint_based",
    "mixed",
    "unclear",
}
VALID_MONITORABILITY = {"high", "medium", "low"}
VALID_CLAIM_TYPES = {
    "growth",
    "margins",
    "demand",
    "valuation",
    "cash_flow",
    "income",
    "macro_tailwind",
    "portfolio_fit",
    "other",
}
VALID_ENTITY_TYPES = {
    "held_company",
    "supplier",
    "customer",
    "competitor",
    "benchmark",
    "macro_series",
    "commodity",
    "sector_proxy",
    "other",
}
VALID_RELATION_TYPES = {
    "depends_on",
    "validated_by",
    "threatened_by",
    "compared_against",
}
VALID_SIGNAL_TYPES = {
    "price_move",
    "revenue_growth",
    "earnings_growth",
    "guidance_change",
    "earnings_surprise",
    "transcript_topic",
    "news_topic",
    "insider_transaction",
    "dividend_change",
    "macro_series_change",
}
VALID_CLAIM_SOURCE_FIELDS = {
    "why_own_it",
    "must_remain_true",
    "what_would_change_my_mind",
}
VAGUE_PATTERNS = (
    r"\bfriend recommended\b",
    r"\brecommended it\b",
    r"\btip from\b",
    r"\beveryone was talking about it\b",
    r"\bnot sure\b",
    r"\bjust because\b",
    r"\bi like the stock\b",
)
DESCRIPTIVE_PATTERNS = (
    r"^\s*they make\b",
    r"^\s*it('?s| is) a\b",
    r"^\s*this company\b",
    r"^\s*they are\b",
)


def normalized_text(value: str | None) -> str:
    return (value or "").strip()


def to_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_vague_thesis(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in VAGUE_PATTERNS) or len(text.split()) < 5


def is_descriptive_only(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in DESCRIPTIVE_PATTERNS)


def normalize_decomposition_output(raw_output: dict[str, Any]) -> dict[str, Any]:
    reason_type = str(raw_output.get("reason_type", "")).strip()
    if reason_type not in VALID_REASON_TYPES:
        reason_type = "unclear"

    monitorability = str(raw_output.get("monitorability", "")).strip()
    if monitorability not in VALID_MONITORABILITY:
        monitorability = "low"

    claims: list[dict[str, Any]] = []
    for position, claim in enumerate(raw_output.get("claims", []) if isinstance(raw_output.get("claims"), list) else [], start=1):
        if not isinstance(claim, dict):
            continue
        claim_text = normalized_text(claim.get("claim_text"))
        if not claim_text:
            continue
        claim_type = str(claim.get("claim_type", "")).strip() or "other"
        if claim_type not in VALID_CLAIM_TYPES:
            claim_type = "other"
        source_field = str(claim.get("source_field", "")).strip() or None
        if source_field not in VALID_CLAIM_SOURCE_FIELDS:
            source_field = None
        entities: list[dict[str, Any]] = []
        for entity in claim.get("entities", []) if isinstance(claim.get("entities"), list) else []:
            if not isinstance(entity, dict):
                continue
            entity_name = normalized_text(entity.get("entity_name"))
            if not entity_name:
                continue
            entity_type = str(entity.get("entity_type", "")).strip() or "other"
            if entity_type not in VALID_ENTITY_TYPES:
                entity_type = "other"
            relation_type = str(entity.get("relation_type", "")).strip() or None
            if relation_type and relation_type not in VALID_RELATION_TYPES:
                relation_type = None
            signals: list[dict[str, Any]] = []
            for signal in entity.get("signals", []) if isinstance(entity.get("signals"), list) else []:
                if not isinstance(signal, dict):
                    continue
                signal_type = str(signal.get("signal_type", "")).strip()
                if signal_type not in VALID_SIGNAL_TYPES:
                    continue
                signals.append(
                    {
                        "signal_type": signal_type,
                        "signal_label": normalized_text(signal.get("signal_label")) or None,
                        "direction": normalized_text(signal.get("direction")).lower() or None,
                        "evidence_scope": normalized_text(signal.get("evidence_scope")).lower() or None,
                        "materiality": normalized_text(signal.get("materiality")).lower() or None,
                        "observable": signal.get("observable") if isinstance(signal.get("observable"), bool) else None,
                        "signal_config_json": signal.get("signal_config_json") if isinstance(signal.get("signal_config_json"), dict) else {},
                        "rationale": normalized_text(signal.get("rationale")) or None,
                        "confidence": to_float(signal.get("confidence")),
                        "confirmation_required": bool(signal.get("confirmation_required", True)),
                        "raw_extraction_json": signal,
                    }
                )
            signals = filter_signal_payloads(
                signals,
                claim_text=claim_text,
                source_field=source_field,
                entity_name=entity_name,
                entity_ticker=normalized_text(entity.get("entity_ticker")).upper() or None,
                entity_type=entity_type,
                relation_type=relation_type,
            )
            entities.append(
                {
                    "entity_name": entity_name,
                    "entity_ticker": normalized_text(entity.get("entity_ticker")).upper() or None,
                    "entity_type": entity_type,
                    "relation_type": relation_type,
                    "rationale": normalized_text(entity.get("rationale")) or None,
                    "confidence": to_float(entity.get("confidence")),
                    "confirmation_required": bool(entity.get("confirmation_required", True)),
                    "raw_extraction_json": entity,
                    "signals": signals[:5],
                }
            )
        entities = cap_claim_signals(entities)
        claims.append(
            {
                "claim_text": claim_text,
                "source_field": source_field,
                "claim_type": claim_type,
                "confidence": to_float(claim.get("confidence")),
                "position": position,
                "raw_extraction_json": claim,
                "entities": entities[:5],
            }
        )

    return {
        "reason_type": reason_type,
        "monitorability": monitorability,
        "decomposition_confidence": to_float(raw_output.get("decomposition_confidence")),
        "claims": claims[:5],
    }
