from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.thesis_claim import ThesisClaim
from app.models.thesis_decomposition import ThesisDecomposition
from app.models.thesis_entity import ThesisEntity
from app.models.thesis_signal import ThesisSignal

EARNINGS_CLAIM_KEYWORDS = {"earnings", "growth", "revenue", "profit", "income", "sales"}
MANAGEMENT_CLAIM_KEYWORDS = {"management", "governance", "leadership", "ceo", "founder", "insider"}


async def load_active_decomposition(
    db: AsyncSession, thesis_id: UUID
) -> ThesisDecomposition | None:
    """Load the latest confirmed decomposition with full claim->entity->signal tree."""
    result = await db.execute(
        select(ThesisDecomposition)
        .where(
            ThesisDecomposition.thesis_id == thesis_id,
            ThesisDecomposition.status.in_(["confirmed", "partially_confirmed"]),
        )
        .order_by(ThesisDecomposition.version.desc())
        .limit(1)
        .options(
            selectinload(ThesisDecomposition.claims)
            .selectinload(ThesisClaim.entities)
            .selectinload(ThesisEntity.signals)
        )
    )
    return result.scalar_one_or_none()


def match_candidates_to_signals(
    candidates: list[dict[str, Any]],
    claims: list[ThesisClaim] | None,
) -> list[dict[str, Any]]:
    """Enrich candidates that don't have signal_id with best-match claim_id."""
    if not claims:
        return candidates

    for candidate in candidates:
        evidence = candidate.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
            candidate["evidence"] = evidence
        if evidence.get("signal_id"):
            continue

        event_type = candidate.get("event_type", "")
        matched_claim = None

        if event_type in ("earnings_surprise", "upcoming_earnings", "earnings_call_transcript"):
            matched_claim = _find_claim_by_type_keywords(claims, EARNINGS_CLAIM_KEYWORDS)
        elif event_type == "news_or_earnings_candidate":
            headline = evidence.get("headline") or candidate.get("description", "")
            matched_claim = _find_claim_by_text_overlap(claims, headline)
        elif event_type == "insider_transaction":
            matched_claim = _find_claim_by_type_keywords(claims, MANAGEMENT_CLAIM_KEYWORDS)

        if matched_claim is None and event_type in ("earnings_surprise", "upcoming_earnings", "earnings_call_transcript", "insider_transaction"):
            sorted_claims = sorted(claims, key=lambda c: c.position)
            if sorted_claims:
                matched_claim = sorted_claims[0]

        if matched_claim is not None:
            evidence["claim_id"] = str(matched_claim.id)

    return candidates


def _find_claim_by_type_keywords(
    claims: list[ThesisClaim],
    keywords: set[str],
) -> ThesisClaim | None:
    for claim in sorted(claims, key=lambda c: c.position):
        claim_type_lower = (claim.claim_type or "").lower()
        claim_text_lower = claim.claim_text.lower()
        for keyword in keywords:
            if keyword in claim_type_lower or keyword in claim_text_lower:
                return claim
    return None


def _find_claim_by_text_overlap(
    claims: list[ThesisClaim],
    text: str,
) -> ThesisClaim | None:
    if not text:
        return None
    text_words = set(re.findall(r"\w{3,}", text.lower()))
    best_claim = None
    best_overlap = 0
    for claim in claims:
        claim_words = set(re.findall(r"\w{3,}", claim.claim_text.lower()))
        overlap = len(text_words & claim_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_claim = claim
    return best_claim if best_overlap > 0 else None


def build_evidence_summary(
    candidate: dict[str, Any],
    claim_text: str | None,
    signal_label: str | None,
    why_own_it: str | None,
) -> str:
    description = candidate.get("description", "")

    if claim_text and signal_label:
        return (
            f'You said: "{claim_text}"\n'
            f"We watched: {signal_label}\n"
            f"What happened: {description}"
        )

    if claim_text:
        return (
            f'You said: "{claim_text}"\n'
            f"What happened: {description}"
        )

    if why_own_it:
        return (
            f'Your reason: "{why_own_it}"\n'
            f"What happened: {description}"
        )

    return description


def determine_verdict(severity: str, candidate: dict | None = None) -> str:
    """Infer verdict from severity and candidate evidence where possible."""
    evidence = (candidate or {}).get("evidence", {}) if candidate else {}
    event_type = (candidate or {}).get("event_type", "") if candidate else ""

    # Earnings surprise: use direction
    if event_type == "earnings_surprise":
        surprise = evidence.get("recent_earnings_surprise_pct")
        if surprise is not None:
            if surprise >= 5:
                return "supports"
            if surprise <= -5:
                return "threatens"
            return "neutral"

    # Metric breaches: explicitly flagged as broken are threats
    if event_type == "metric_threshold_breach":
        return "threatens"

    # Severity-based fallback
    if severity == "thesis_breaking":
        return "threatens"
    if severity == "warning":
        return "review"
    if severity == "info":
        return "neutral"
    return "review"
