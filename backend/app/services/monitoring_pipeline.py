from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.thesis import Thesis
from app.services.ai_monitor import classify_event
from app.services.conviction_log import EVIDENCE_RECEIVED, append_log_entry
from app.services.noise_filter import EVIDENCE_TYPE_MAP, record_signal_fired
from app.services.signal_matching import build_evidence_summary, determine_verdict


def build_claim_signal_lookup(claims: list[Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    claims_by_id: dict[str, Any] = {}
    signals_by_id: dict[str, Any] = {}
    if not claims:
        return claims_by_id, signals_by_id

    for claim in claims:
        claims_by_id[str(claim.id)] = claim
        for entity in claim.entities:
            for signal in entity.signals:
                signals_by_id[str(signal.id)] = signal
    return claims_by_id, signals_by_id


def candidate_description_for_classifier(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence", {})
    event_desc = candidate["description"]
    proxy_rationale = evidence.get("proxy_rationale")
    proxy_signal_hint = evidence.get("proxy_signal_hint")
    if proxy_rationale:
        event_desc += f"\nWhy this proxy matters to the thesis: {proxy_rationale}"
    if proxy_signal_hint:
        event_desc += f"\nWhat to look for: {proxy_signal_hint}"
    return event_desc


def candidate_summary_for_storage(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence", {})
    stored_summary = candidate["description"]
    proxy_rationale = evidence.get("proxy_rationale")
    proxy_signal_hint = evidence.get("proxy_signal_hint")
    if proxy_rationale:
        stored_summary += f"\nWhy this matters: {proxy_rationale}"
    if proxy_signal_hint:
        stored_summary += f"\nWhat to look for: {proxy_signal_hint}"
    return stored_summary


async def classify_candidates_for_thesis(
    thesis: Thesis,
    candidates: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], str, str | None]]:
    classified: list[tuple[dict[str, Any], str, str | None]] = []
    for candidate in candidates:
        classification = await classify_event(
            why_own_it=thesis.why_own_it,
            must_remain_true=thesis.must_remain_true,
            what_would_change_my_mind=thesis.what_would_change_my_mind,
            ai_summary=thesis.ai_summary,
            event_description=candidate_description_for_classifier(candidate),
        )
        severity = classification.severity if classification else "warning"
        ai_analysis = classification.analysis if classification else None
        classified.append((candidate, severity, ai_analysis))
    return classified


async def persist_classified_candidates(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    classified: list[tuple[dict[str, Any], str, str | None]],
    claims_by_id: dict[str, Any],
    signals_by_id: dict[str, Any],
    now,
) -> list[uuid.UUID]:
    events: list[MonitoringEvent] = []
    for candidate, severity, ai_analysis in classified:
        evidence = candidate.get("evidence", {})
        source_url = evidence.get("url")

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
        stored_summary = candidate_summary_for_storage(candidate)

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
        events.append(event)
        await record_signal_fired(evidence_signal_id, signals_by_id, now=now)
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=thesis.user_id,
            entry_type=EVIDENCE_RECEIVED,
            content=evidence_summary or stored_summary[:300],
            metadata={"event_type": candidate["event_type"], "severity": severity},
            claim_id=uuid.UUID(evidence_claim_id) if evidence_claim_id else None,
            signal_id=uuid.UUID(evidence_signal_id) if evidence_signal_id else None,
        )

        if severity == "thesis_breaking" and thesis.status in ("active", "draft"):
            thesis.status = "needs_review"

    if events:
        await db.flush()
    return [event.id for event in events]
