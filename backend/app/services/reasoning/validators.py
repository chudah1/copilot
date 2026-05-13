from typing import Any

from app.services.reasoning.normalizers import is_descriptive_only, is_vague_thesis


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
