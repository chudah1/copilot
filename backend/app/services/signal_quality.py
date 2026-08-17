"""Phase 2 signal contract and deterministic quality controls.

The model suggests signals; this module decides whether a suggestion is
specific and safe enough to enter the monitoring graph. Keeping these checks
deterministic prevents a second model call from becoming the source of truth.
"""

import re
from typing import Any


VALID_SIGNAL_DIRECTIONS = {"supports", "threatens"}
VALID_EVIDENCE_SCOPES = {"company", "industry", "market", "macro", "competitor"}
VALID_MATERIALITY = {"low", "medium", "high"}

_SIGNAL_WORDS = {
    "price_move": "price move",
    "revenue_growth": "revenue growth",
    "earnings_growth": "earnings growth",
    "guidance_change": "guidance change",
    "earnings_surprise": "earnings surprise",
    "transcript_topic": "management commentary",
    "news_topic": "company news",
    "insider_transaction": "insider transactions",
    "dividend_change": "dividend change",
    "macro_series_change": "macro trend",
}
_GENERIC_SIGNAL_TAILS = {
    "business model",
    "competitive advantage",
    "fundamentals",
    "market opportunity",
    "moat",
    "the moat",
    "the story",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _canonical(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).strip()


def _default_direction(*, source_field: str | None, relation_type: str | None) -> str:
    if source_field == "what_would_change_my_mind" or relation_type == "threatened_by":
        return "threatens"
    return "supports"


def _default_scope(entity_type: str | None) -> str:
    return {
        "held_company": "company",
        "supplier": "industry",
        "customer": "industry",
        "competitor": "competitor",
        "benchmark": "market",
        "macro_series": "macro",
        "commodity": "macro",
        "sector_proxy": "industry",
    }.get(entity_type or "", "company")


def _default_materiality(confidence: float | None) -> str:
    if confidence is not None and confidence >= 0.85:
        return "high"
    if confidence is not None and confidence < 0.6:
        return "low"
    return "medium"


def _label_for_signal(
    signal: dict[str, Any],
    *,
    entity_name: str | None,
    entity_ticker: str | None,
) -> str:
    label = _clean(signal.get("signal_label"))
    subject = _clean(entity_ticker).upper() or _clean(entity_name)
    if not label:
        label = _SIGNAL_WORDS.get(_clean(signal.get("signal_type")), "investment signal")
    if subject and _canonical(subject) not in _canonical(label):
        label = f"{subject} {label}"
    return label[:255]


def signal_identity(signal: dict[str, Any]) -> tuple[str, str]:
    """Return a stable identity that ignores wording/casing differences."""
    config = signal.get("signal_config_json") if isinstance(signal.get("signal_config_json"), dict) else {}
    discriminator = (
        config.get("metric")
        or config.get("topic")
        or config.get("watch_for")
        or signal.get("signal_label")
        or signal.get("signal_type")
    )
    return _clean(signal.get("signal_type")), _canonical(discriminator)


def prepare_signal(
    signal: dict[str, Any],
    *,
    claim_text: str | None,
    source_field: str | None,
    entity_name: str | None,
    entity_ticker: str | None,
    entity_type: str | None,
    relation_type: str | None,
) -> dict[str, Any]:
    """Enrich one provider signal with the Phase 2 monitoring contract."""
    prepared = dict(signal)
    confidence = signal.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None

    direction = _clean(signal.get("direction")).lower()
    if direction not in VALID_SIGNAL_DIRECTIONS:
        direction = _default_direction(source_field=source_field, relation_type=relation_type)

    evidence_scope = _clean(signal.get("evidence_scope")).lower()
    if evidence_scope not in VALID_EVIDENCE_SCOPES:
        evidence_scope = _default_scope(entity_type)

    materiality = _clean(signal.get("materiality")).lower()
    if materiality not in VALID_MATERIALITY:
        materiality = _default_materiality(confidence)

    observable = signal.get("observable")
    if not isinstance(observable, bool):
        observable = True

    label = _label_for_signal(signal, entity_name=entity_name, entity_ticker=entity_ticker)
    rationale = _clean(signal.get("rationale"))
    if not rationale:
        rationale = f"Tests whether {claim_text or label} remains true."

    issues: list[str] = []
    if not observable:
        issues.append("not_observable")
    if len(_canonical(label).split()) < 2:
        issues.append("not_specific")
    canonical_label = _canonical(label)
    subject_tokens = {_canonical(entity_ticker), _canonical(entity_name)} - {""}
    label_tail = canonical_label
    for subject in sorted(subject_tokens, key=len, reverse=True):
        label_tail = label_tail.removeprefix(subject).strip()
    if label_tail in _GENERIC_SIGNAL_TAILS:
        issues.append("not_specific")
    if signal.get("signal_type") in {"news_topic", "transcript_topic"}:
        config = signal.get("signal_config_json") if isinstance(signal.get("signal_config_json"), dict) else {}
        if not _clean(config.get("topic") or config.get("watch_for")):
            issues.append("missing_topic")

    prepared["signal_label"] = label
    prepared["rationale"] = rationale
    prepared["direction"] = direction
    prepared["evidence_scope"] = evidence_scope
    prepared["materiality"] = materiality
    prepared["observable"] = observable
    prepared["quality"] = {
        "status": "review" if issues else "ready",
        "issues": issues,
        "specific": "not_specific" not in issues,
        "causal": bool(rationale),
        "material": materiality != "low",
    }
    return prepared


def filter_signal_payloads(
    signals: list[dict[str, Any]],
    *,
    claim_text: str | None,
    source_field: str | None,
    entity_name: str | None,
    entity_ticker: str | None,
    entity_type: str | None,
    relation_type: str | None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Dedupe and cap signals while retaining the most material suggestions."""
    prepared: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        item = prepare_signal(
            signal,
            claim_text=claim_text,
            source_field=source_field,
            entity_name=entity_name,
            entity_ticker=entity_ticker,
            entity_type=entity_type,
            relation_type=relation_type,
        )
        key = signal_identity(item)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        prepared.append(item)

    # Keep model ordering for equal scores; materiality only prevents a low
    # value duplicate from crowding out the core watch for a claim.
    prepared.sort(
        key=lambda item: (
            item.get("materiality") == "high",
            item.get("materiality") == "medium",
            float(item.get("confidence") or 0),
        ),
        reverse=True,
    )
    return prepared[:limit]


def cap_claim_signals(entities: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Apply the signal cap across all entities belonging to one claim."""
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for entity in entities:
        for signal in entity.get("signals", []):
            key = signal_identity(signal)
            if not key[0] or key in seen:
                continue
            seen.add(key)
            candidates.append((entity, signal))

    candidates.sort(
        key=lambda pair: (
            pair[1].get("materiality") == "high",
            pair[1].get("materiality") == "medium",
            float(pair[1].get("confidence") or 0),
        ),
        reverse=True,
    )
    selected = {id(signal) for _, signal in candidates[:limit]}
    for entity in entities:
        entity["signals"] = [signal for signal in entity.get("signals", []) if id(signal) in selected]
    return entities
