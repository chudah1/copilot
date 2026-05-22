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
    severity: str | None = None,
    verdict: str | None = None,
    investor_profile: str | None = None,
) -> str:
    description = candidate.get("description", "")
    watched_text = signal_label or claim_text
    implication = _build_event_implication(
        claim_text=claim_text,
        signal_label=signal_label,
        severity=severity,
        verdict=verdict,
    )
    decision = _build_event_decision(
        severity=severity,
        verdict=verdict,
        investor_profile=investor_profile,
    )

    lines: list[str] = []

    if investor_profile == "thesis_driven":
        if claim_text and watched_text:
            lines.extend(
                [
                    f'Your thesis: "{claim_text}"',
                    f"We were watching: {watched_text}",
                ]
            )
        elif claim_text:
            lines.append(f'Your thesis: "{claim_text}"')
        elif why_own_it:
            lines.append(f'Your thesis: "{why_own_it}"')

    elif investor_profile == "hearsay_driven":
        if claim_text and watched_text:
            lines.extend(
                [
                    f'Your reason: "{claim_text}"',
                    f"We were watching: {watched_text}",
                ]
            )
        elif claim_text:
            lines.append(f'Your reason: "{claim_text}"')
        elif why_own_it:
            lines.append(f'Your reason: "{why_own_it}"')
    else:
        if claim_text and signal_label:
            lines.extend(
                [
                    f'You said: "{claim_text}"',
                    f"We watched: {signal_label}",
                ]
            )
        elif claim_text:
            lines.append(f'You said: "{claim_text}"')
        elif why_own_it:
            lines.append(f'Your reason: "{why_own_it}"')

    if not lines and severity is None and verdict is None:
        return description

    lines.append(description if lines else description)
    if implication:
        lines.append(implication)
    if decision:
        lines.append(decision)
    return "\n".join(lines)


def _build_event_implication(
    *,
    claim_text: str | None,
    signal_label: str | None,
    severity: str | None,
    verdict: str | None,
) -> str:
    watched_text = signal_label or claim_text
    if severity == "thesis_breaking" or verdict == "threatens":
        if watched_text:
            return f"This directly threatens the part of the thesis tied to {watched_text}."
        return "This directly threatens a core part of the original investment case."
    if severity == "warning" or verdict == "review":
        if watched_text:
            return f"This is relevant because it tests whether {watched_text} is still holding up."
        return "This is relevant because it tests whether the original reason still holds up."
    if watched_text:
        return f"This is useful evidence for the part of the thesis tied to {watched_text}, but it is not a clear break yet."
    return "This is useful evidence, but it is not a clear break yet."


def _build_event_decision(
    *,
    severity: str | None,
    verdict: str | None,
    investor_profile: str | None,
) -> str:
    if severity == "thesis_breaking" or verdict == "threatens":
        if investor_profile == "thesis_driven":
            return "Re-read the thesis and decide whether to rewrite or exit before you add, trim, or wave it off."
        if investor_profile == "hearsay_driven":
            return "Pressure-test whether the original story still deserves a place in the portfolio."
        return "Review the position now and decide whether the original case is still intact."
    if severity == "warning" or verdict == "review":
        if investor_profile == "thesis_driven":
            return "Review this thesis pillar before averaging up, averaging down, or dismissing the change."
        if investor_profile == "hearsay_driven":
            return "Check whether the story is becoming more real or starting to break down."
        return "Review whether this changes your confidence or next action on the position."
    if investor_profile == "thesis_driven":
        return "Keep watching, but this does not yet require rewriting the thesis."
    if investor_profile == "hearsay_driven":
        return "Keep watching, but this alone does not mean the original story is broken."
    return "Keep watching, but this does not yet require a decision change."


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
