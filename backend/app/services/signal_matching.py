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

# Used by upcoming_earnings + earnings_call_transcript events, which reveal
# both top-line (revenue) and bottom-line (EPS) results.
EARNINGS_CLAIM_KEYWORDS = {"earnings", "growth", "revenue", "profit", "income", "sales"}
EARNINGS_SIGNAL_TYPES = {"revenue_growth", "earnings_growth", "earnings_surprise", "guidance_change"}

# Narrower set for `earnings_surprise` events specifically. The +5.6% surprise
# is an EPS surprise (bottom-line), not a revenue surprise (top-line), so it
# shouldn't be evidence for a "segment revenue grows X%" claim — different
# metric. Walkthrough on 2026-06-14 found the broader pool was misattributing
# beats to revenue claims. See [[project_e2e_walkthrough_2026_06_14]].
# Short keywords like "eps" would substring-match inside common words like
# "keeps" or "depositary"; the matcher does a plain `in` check, not a word-
# boundary one. Stick to keywords long enough to be safe.
EPS_CLAIM_KEYWORDS = {"earnings", "profit", "income", "margin"}
EPS_SIGNAL_TYPES = {"earnings_growth", "earnings_surprise", "guidance_change"}

MANAGEMENT_CLAIM_KEYWORDS = {"management", "governance", "leadership", "ceo", "founder", "insider"}
MANAGEMENT_SIGNAL_TYPES = {"insider_transaction"}
NEWS_SIGNAL_TYPES = {"news_topic", "news_watch"}


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
    """Enrich candidates with the sharpest available claim/signal attribution."""
    if not claims:
        return candidates
    active_signals = _collect_active_signals(claims)

    for candidate in candidates:
        evidence = candidate.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
            candidate["evidence"] = evidence
        if evidence.get("signal_id"):
            # Already pre-bound by upstream (e.g. metric_threshold breach).
            # Record the single signal in the multi-binding list too so
            # downstream readers can rely on the list consistently.
            _ensure_multi_binding_includes_primary(evidence, active_signals)
            continue

        event_type = candidate.get("event_type", "")
        matched_signal = _find_best_signal_match(active_signals, candidate)
        matched_claim = None

        if matched_signal is not None:
            matched_claim, signal = matched_signal
            evidence["signal_id"] = str(signal.id)
            # Multi-binding: a Gemini article often carries 3-4 relevant_signals
            # labels that all touch the thesis. Surface them all so the
            # conviction log / digest / dashboard can attribute the event to
            # every signal it actually touches, instead of just the primary.
            _record_all_matching_signals(evidence, active_signals, candidate, signal)
        elif event_type == "earnings_surprise":
            matched_claim = _find_claim_by_type_keywords(claims, EPS_CLAIM_KEYWORDS)
        elif event_type in ("upcoming_earnings", "earnings_call_transcript"):
            matched_claim = _find_claim_by_type_keywords(claims, EARNINGS_CLAIM_KEYWORDS)
        elif event_type in {"news_or_earnings_candidate", "product_ramp_update", "gemini_news", "news_keyword_match", "edgar_8k"}:
            headline = evidence.get("headline") or candidate.get("description", "")
            matched_claim = _find_claim_by_text_overlap(claims, headline)
        elif event_type == "insider_transaction":
            matched_claim = _find_claim_by_type_keywords(claims, MANAGEMENT_CLAIM_KEYWORDS)

        # Fallback to first claim is acceptable for events whose attribution is
        # naturally fuzzy (an upcoming-earnings event or a transcript covers
        # everything), but earnings_surprise is metric-specific: if there is no
        # EPS/profit/margin claim, leaving claim_id unset is better than
        # falsely binding it to a top-line revenue claim.
        if matched_claim is None and event_type in ("upcoming_earnings", "earnings_call_transcript", "insider_transaction"):
            sorted_claims = sorted(claims, key=lambda c: c.position)
            if sorted_claims:
                matched_claim = sorted_claims[0]

        if matched_claim is not None:
            evidence["claim_id"] = str(matched_claim.id)

    return candidates


def _collect_active_signals(
    claims: list[ThesisClaim],
) -> list[tuple[ThesisClaim, ThesisSignal]]:
    active_signals: list[tuple[ThesisClaim, ThesisSignal]] = []
    for claim in claims:
        for entity in getattr(claim, "entities", []) or []:
            for signal in getattr(entity, "signals", []) or []:
                if getattr(signal, "active", False):
                    active_signals.append((claim, signal))
    return active_signals


def _record_all_matching_signals(
    evidence: dict[str, Any],
    active_signals: list[tuple[ThesisClaim, ThesisSignal]],
    candidate: dict[str, Any],
    primary_signal: ThesisSignal,
) -> None:
    """Surface every active signal this candidate touches into matched_signal_ids
    and matched_signal_labels. The primary signal_id stays as the single 'best
    match' anchor for backward-compat readers; the list captures the multi-pillar
    attribution that single-valued binding throws away."""
    matched_pairs: list[tuple[str, str]] = []
    seen_ids: set[str] = set()

    # 1. Start with the primary so it appears first in the list.
    primary_id = str(primary_signal.id)
    primary_label = str(getattr(primary_signal, "signal_label", None) or "").strip()
    matched_pairs.append((primary_id, primary_label))
    seen_ids.add(primary_id)

    # 2. Add every active signal whose label appears in evidence.relevant_signals
    # (Gemini's explicit per-signal attribution, when available).
    relevant_labels = evidence.get("relevant_signals")
    if isinstance(relevant_labels, list):
        wanted = {_normalize_text(str(lbl)) for lbl in relevant_labels if str(lbl).strip()}
        if wanted:
            for _, signal in active_signals:
                sid = str(signal.id)
                if sid in seen_ids:
                    continue
                label = str(getattr(signal, "signal_label", None) or "").strip()
                if label and _normalize_text(label) in wanted:
                    matched_pairs.append((sid, label))
                    seen_ids.add(sid)

    # 3. Add every other active signal whose word-overlap score exceeds the
    # same floor used by _find_best_signal_match. Threshold > 0 keeps this
    # to genuine matches, not "any signal shares a stopword with the headline".
    event_type = candidate.get("event_type", "")
    candidate_text = _candidate_match_text(candidate)
    for claim, signal in active_signals:
        sid = str(signal.id)
        if sid in seen_ids:
            continue
        score = _signal_match_score(event_type, candidate_text, claim, signal)
        if score <= 0:
            continue
        label = str(getattr(signal, "signal_label", None) or "").strip()
        matched_pairs.append((sid, label))
        seen_ids.add(sid)

    evidence["matched_signal_ids"] = [sid for sid, _ in matched_pairs]
    evidence["matched_signal_labels"] = [label for _, label in matched_pairs if label]


def _ensure_multi_binding_includes_primary(
    evidence: dict[str, Any],
    active_signals: list[tuple[ThesisClaim, ThesisSignal]],
) -> None:
    """When evidence.signal_id was set by an upstream stage (e.g. price_move,
    watch_hint_breach, news_watch), the multi-binding list may not be present
    yet. Ensure it includes at minimum the primary so downstream readers can
    rely on the list."""
    primary_id = evidence.get("signal_id")
    if not primary_id:
        return
    existing_ids = evidence.get("matched_signal_ids")
    if isinstance(existing_ids, list) and str(primary_id) in {str(x) for x in existing_ids}:
        return
    primary_label = ""
    for _, signal in active_signals:
        if str(signal.id) == str(primary_id):
            primary_label = str(getattr(signal, "signal_label", None) or "").strip()
            break
    evidence["matched_signal_ids"] = [str(primary_id)]
    if primary_label:
        evidence["matched_signal_labels"] = [primary_label]


def _find_best_signal_match(
    active_signals: list[tuple[ThesisClaim, ThesisSignal]],
    candidate: dict[str, Any],
) -> tuple[ThesisClaim, ThesisSignal] | None:
    if not active_signals:
        return None

    evidence = candidate.get("evidence") or {}
    exact_label_match = _find_signal_by_relevant_labels(active_signals, evidence.get("relevant_signals"))
    if exact_label_match is not None:
        return exact_label_match

    event_type = candidate.get("event_type", "")
    candidate_text = _candidate_match_text(candidate)
    best: tuple[int, ThesisClaim, ThesisSignal] | None = None

    for claim, signal in active_signals:
        score = _signal_match_score(event_type, candidate_text, claim, signal)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, claim, signal)

    return (best[1], best[2]) if best is not None else None


def _find_signal_by_relevant_labels(
    active_signals: list[tuple[ThesisClaim, ThesisSignal]],
    relevant_labels: Any,
) -> tuple[ThesisClaim, ThesisSignal] | None:
    if not isinstance(relevant_labels, list):
        return None
    wanted = {_normalize_text(str(label)) for label in relevant_labels if str(label).strip()}
    if not wanted:
        return None
    for claim, signal in active_signals:
        signal_label = getattr(signal, "signal_label", None)
        if signal_label and _normalize_text(signal_label) in wanted:
            return (claim, signal)
    return None


def _candidate_match_text(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence") or {}
    parts = [
        evidence.get("headline"),
        evidence.get("summary"),
        evidence.get("description"),
        candidate.get("description"),
    ]
    return " ".join(str(part).strip() for part in parts if part).strip()


def _signal_match_score(
    event_type: str,
    candidate_text: str,
    claim: ThesisClaim,
    signal: ThesisSignal,
) -> int:
    signal_type = str(getattr(signal, "signal_type", "") or "")
    signal_words = _words(_signal_match_text(claim, signal))
    candidate_words = _words(candidate_text)
    overlap = len(signal_words & candidate_words)

    if event_type == "earnings_surprise":
        # Narrow family: an EPS surprise is bottom-line evidence, not top-line.
        family_bonus = 4 if signal_type in EPS_SIGNAL_TYPES else 1 if overlap > 0 else 0
        return family_bonus + overlap * 10

    if event_type in {"upcoming_earnings", "earnings_call_transcript"}:
        family_bonus = 4 if signal_type in EARNINGS_SIGNAL_TYPES else 1 if overlap > 0 else 0
        return family_bonus + overlap * 10

    if event_type == "insider_transaction":
        family_bonus = 4 if signal_type in MANAGEMENT_SIGNAL_TYPES else 2 if _has_management_words(signal_words) else 0
        return family_bonus + overlap * 10

    if event_type in {"news_or_earnings_candidate", "product_ramp_update", "gemini_news", "news_keyword_match", "edgar_8k"}:
        family_bonus = 2 if signal_type in NEWS_SIGNAL_TYPES else 0
        return family_bonus + overlap * 10

    return 0


def _signal_match_text(claim: ThesisClaim, signal: ThesisSignal) -> str:
    parts = [
        getattr(signal, "signal_label", None),
        getattr(signal, "rationale", None),
        getattr(claim, "claim_text", None),
        str(getattr(signal, "signal_type", "") or "").replace("_", " "),
    ]
    return " ".join(str(part).strip() for part in parts if part).strip()


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w{3,}", text.lower()))


def _normalize_text(text: str) -> str:
    return " ".join(_words(text))


def _has_management_words(words: set[str]) -> bool:
    return bool(words & MANAGEMENT_CLAIM_KEYWORDS)


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

    lines.append(f"What changed: {description}")
    if implication:
        lines.append(f"Why it matters now: {implication}")
    if decision:
        lines.append(f"Next step: {decision}")
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

    # Qualitative news_watch carries its own direction.
    news_watch_direction = evidence.get("news_watch_direction")
    if news_watch_direction == "supports":
        return "supports"
    if news_watch_direction == "threatens":
        return "threatens"

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
    if event_type == "metric_threshold":
        return "threatens"

    # Severity-based fallback
    if severity == "thesis_breaking":
        return "threatens"
    if severity == "warning":
        return "review"
    if severity == "info":
        return "neutral"
    return "review"
