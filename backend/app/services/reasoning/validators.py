from typing import Any

from app.services.reasoning.normalizers import is_descriptive_only, is_vague_thesis


ENTITY_SIGNAL_ALLOWLIST: dict[str, set[str]] = {
    "held_company": {
        "price_move",
        "revenue_growth",
        "earnings_growth",
        "guidance_change",
        "earnings_surprise",
        "transcript_topic",
        "news_topic",
        "insider_transaction",
        "dividend_change",
    },
    "supplier": {
        "price_move",
        "revenue_growth",
        "earnings_growth",
        "guidance_change",
        "earnings_surprise",
        "transcript_topic",
        "news_topic",
        "insider_transaction",
        "dividend_change",
    },
    "customer": {
        "price_move",
        "revenue_growth",
        "earnings_growth",
        "guidance_change",
        "earnings_surprise",
        "transcript_topic",
        "news_topic",
        "insider_transaction",
        "dividend_change",
    },
    "competitor": {
        "price_move",
        "revenue_growth",
        "earnings_growth",
        "guidance_change",
        "earnings_surprise",
        "transcript_topic",
        "news_topic",
        "insider_transaction",
        "dividend_change",
    },
    "benchmark": {"price_move", "macro_series_change", "news_topic"},
    "macro_series": {"macro_series_change", "news_topic"},
    "commodity": {"price_move", "macro_series_change", "news_topic"},
    "sector_proxy": {"price_move", "macro_series_change", "news_topic"},
}

CLAIM_SIGNAL_ALLOWLIST: dict[str, set[str]] = {
    "growth": {"price_move", "revenue_growth", "earnings_growth", "guidance_change", "earnings_surprise", "transcript_topic", "news_topic"},
    "margins": {"earnings_growth", "guidance_change", "transcript_topic", "news_topic"},
    "demand": {"revenue_growth", "guidance_change", "earnings_surprise", "transcript_topic", "news_topic"},
    "valuation": {"price_move", "earnings_growth", "dividend_change", "macro_series_change", "news_topic"},
    "cash_flow": {"earnings_growth", "dividend_change", "guidance_change", "transcript_topic", "news_topic"},
    "income": {"dividend_change", "earnings_growth", "price_move", "news_topic"},
    "macro_tailwind": {"macro_series_change", "price_move", "news_topic"},
    "portfolio_fit": {"price_move", "news_topic"},
}


def _invalid_mapping_reason(normalized_output: dict[str, Any]) -> str | None:
    for claim in normalized_output.get("claims", []):
        claim_type = claim.get("claim_type")
        allowed_for_claim = CLAIM_SIGNAL_ALLOWLIST.get(str(claim_type)) if claim_type else None
        for entity in claim.get("entities", []):
            entity_type = entity.get("entity_type")
            allowed_for_entity = ENTITY_SIGNAL_ALLOWLIST.get(str(entity_type)) if entity_type else None
            for signal in entity.get("signals", []):
                signal_type = signal.get("signal_type")
                if allowed_for_entity is not None and signal_type not in allowed_for_entity:
                    return f"Signal {signal_type} is not a sensible match for entity type {entity_type}"
                if allowed_for_claim is not None and signal_type not in allowed_for_claim:
                    return f"Signal {signal_type} is not a sensible match for claim type {claim_type}"
    return None


def validate_decomposition_output(
    normalized_output: dict[str, Any] | None,
    *,
    original_text: str,
) -> tuple[bool, str | None]:
    if not isinstance(normalized_output, dict):
        return False, "Normalized output missing"
    if "claims" not in normalized_output or not isinstance(normalized_output["claims"], list):
        return False, "Claims missing from normalized output"
    if not normalized_output.get("reason_type"):
        return False, "Reason type missing"
    if not normalized_output.get("monitorability"):
        return False, "Monitorability missing"
    if is_descriptive_only(original_text):
        signal_count = sum(
            len(entity.get("signals", []))
            for claim in normalized_output["claims"]
            for entity in claim.get("entities", [])
        )
        if signal_count > 0:
            return False, "Descriptive-only thesis should not produce monitorable signals"
    invalid_mapping = _invalid_mapping_reason(normalized_output)
    if invalid_mapping:
        return False, invalid_mapping
    return True, None


def output_needs_escalation(
    normalized_output: dict[str, Any] | None,
    *,
    original_text: str,
) -> tuple[bool, str | None]:
    if not isinstance(normalized_output, dict):
        return True, "Missing normalized output"
    claims = normalized_output.get("claims", [])
    if not claims and not is_vague_thesis(original_text):
        return True, "No claims extracted from non-vague thesis"
    confidence = normalized_output.get("decomposition_confidence")
    if confidence is not None and confidence < 0.55:
        return True, "Decomposition confidence too low"
    proxy_entities = [
        entity
        for claim in claims
        for entity in claim.get("entities", [])
        if entity.get("entity_type") not in {None, "held_company", "other"}
    ]
    if proxy_entities and (confidence is None or confidence < 0.65):
        return True, "Proxy-heavy decomposition requires higher confidence"
    return False, None
