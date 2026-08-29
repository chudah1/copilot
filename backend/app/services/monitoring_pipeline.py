from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)

_SCORE_THRESHOLD = 0.30
_MAX_SENTENCES = 8
_TRANSCRIPT_LOOKBACK = 2

# Objective threshold breaches that should fire regardless of the AI classifier
# (they test a number against the user's own threshold — no judgment needed).
DETERMINISTIC_BREACH_EVENT_TYPES = {"price_move", "metric_threshold"}

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.holding import Holding
from app.models.monitoring_event import MonitoringEvent
from app.models.onboarding_state import OnboardingState
from app.models.thesis import Thesis
from app.services.ai_monitor import classify_event
from app.services.conviction_log import EVIDENCE_RECEIVED, append_log_entry
from app.services.embeddings import embed_texts
from app.services.news_watch import (
    NEWS_LIKE_EVENT_TYPES,
    NewsWatch,
    build_embedding_similarity,
    candidate_text,
    expand_watch_queries,
    judge_news_watch,
    match_news_watches,
)
from app.services.noise_filter import (
    COOLDOWN_HOURS,
    DEFAULT_COOLDOWN_HOURS,
    EVIDENCE_TYPE_MAP,
    _story_anchor_uses_cooldown,
    record_signal_fired,
    story_anchor_for_candidate,
)
from app.services.signal_matching import build_evidence_summary, determine_verdict
from app.services.text_cleaning import clean_text


def _candidate_log_detail(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence", {}) if isinstance(candidate.get("evidence"), dict) else {}
    detail = (
        evidence.get("headline")
        or evidence.get("description")
        or candidate.get("description")
        or ""
    )
    return str(detail).replace("\n", " ")[:160]


async def _acquire_story_anchor_lock(
    db: AsyncSession,
    *,
    holding_id: uuid.UUID,
    story_anchor: str,
) -> None:
    """Serialize PostgreSQL writers for one holding/story pair."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    await db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:anchor_lock_key, 0))"
        ),
        {"anchor_lock_key": f"{holding_id}:{story_anchor}"},
    )


def _event_title(ticker: str, candidate: dict[str, Any], claim_obj: Any | None) -> str:
    event_type = candidate.get("event_type", "")
    evidence = candidate.get("evidence", {})
    clean = ticker.replace("_US_EQ", "").replace("_EQ", "")

    if event_type == "earnings_surprise":
        surprise = evidence.get("recent_earnings_surprise_pct")
        if surprise is not None:
            direction = "beat" if surprise >= 0 else "missed"
            return f"{clean} earnings {direction} by {abs(surprise):.1f}%"
        return f"{clean} reported earnings"

    if event_type == "metric_threshold":
        metric = evidence.get("metric", "").replace("_", " ")
        return f"{clean}: {metric} threshold breached" if metric else f"{clean} metric alert"

    if event_type in ("news_or_earnings_candidate", "product_ramp_update", "news_keyword_match"):
        # Prefer the actual headline so two events about different articles
        # look different in the UI. The previous "news touches '{claim_text}'"
        # template made every news event for the same claim look identical —
        # caught during the onboarding walkthrough where 4 different articles
        # rendered with the same title and confused dedup at-a-glance.
        headline = (evidence.get("headline") or "").strip()
        if headline:
            return f"{clean}: {headline[:80]}"
        if claim_obj:
            return f"{clean}: news touches '{claim_obj.claim_text[:50]}'"
        return f"{clean}: relevant news"

    if event_type == "upcoming_earnings":
        return f"{clean} reports earnings soon"

    if event_type == "insider_transaction":
        return f"{clean}: insider activity"

    if event_type == "edgar_8k":
        desc = evidence.get("description", "new event")
        return f"{clean}: SEC 8-K — {desc}"

    if event_type == "gemini_news":
        headline = evidence.get("headline", "")
        return f"{clean}: {headline[:80]}" if headline else f"{clean}: news"

    return f"{clean}: {event_type.replace('_', ' ')}"


def signal_labels_from_claims(claims: list[Any] | None) -> list[str]:
    """Extract all active signal labels from a decomposition's claim list."""
    if not claims:
        return []
    return [
        signal.signal_label
        for claim in claims
        for entity in (claim.entities or [])
        for signal in (entity.signals or [])
        if signal.signal_label
    ]


def signal_search_descriptors_from_claims(claims: list[Any] | None) -> list[dict[str, str]]:
    """Extract reusable search descriptors for signal-aware news retrieval."""
    if not claims:
        return []

    descriptors: list[dict[str, str]] = []
    for claim in claims:
        claim_text = str(getattr(claim, "claim_text", "") or "").strip()
        for entity in (claim.entities or []):
            for signal in (entity.signals or []):
                label = str(getattr(signal, "signal_label", "") or "").strip()
                if not label:
                    continue
                rationale = str(getattr(signal, "rationale", "") or "").strip()
                descriptors.append(
                    {
                        "label": label,
                        "claim_text": claim_text,
                        "rationale": rationale,
                    }
                )
    return descriptors


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
    event_desc = clean_text(candidate.get("description"))
    proxy_rationale = evidence.get("proxy_rationale")
    proxy_signal_hint = evidence.get("proxy_signal_hint")
    if proxy_rationale:
        event_desc += f"\nWhy this proxy matters to the thesis: {proxy_rationale}"
    if proxy_signal_hint:
        event_desc += f"\nWhat to look for: {proxy_signal_hint}"
    return event_desc


def candidate_summary_for_storage(candidate: dict[str, Any]) -> str:
    evidence = candidate.get("evidence", {})
    stored_summary = clean_text(candidate.get("description"))
    proxy_rationale = evidence.get("proxy_rationale")
    proxy_signal_hint = evidence.get("proxy_signal_hint")
    if proxy_rationale:
        stored_summary += f"\nWhy this matters: {proxy_rationale}"
    if proxy_signal_hint:
        stored_summary += f"\nWhat to look for: {proxy_signal_hint}"
    return stored_summary


async def _thesis_aware_highlights(
    full_text: str,
    why_own_it: str | None,
    must_remain_true: str | None,
    what_would_change_my_mind: str | None,
) -> list[str] | None:
    """Return thesis-relevant sentences from a transcript."""
    claim_texts = [t for t in [why_own_it, must_remain_true, what_would_change_my_mind] if t and t.strip()]
    return await _relevant_transcript_highlights(full_text, claim_texts)


def _word_overlap_score(a: str, b: str) -> float:
    aw = {w for w in re.findall(r"\w{4,}", a.lower())}
    bw = {w for w in re.findall(r"\w{4,}", b.lower())}
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


async def _relevant_transcript_highlights(
    full_text: str,
    focus_texts: list[str],
) -> list[str] | None:
    """Return transcript sentences most relevant to the supplied focus texts.

    Used in two places:
    - thesis-aware transcript summarisation before generic classification
    - signal-aware transcript enrichment before qualitative watch matching
    """
    try:
        focus_texts = [t for t in focus_texts if t and t.strip()]
        if not focus_texts:
            return None

        windows = _build_transcript_windows(full_text)
        if not windows:
            return None

        if not settings.openai_api_key:
            scored: list[tuple[float, str, int]] = []
            for idx, (sentence, window_text) in enumerate(windows):
                score = max(_word_overlap_score(window_text, focus) for focus in focus_texts)
                if score > 0:
                    scored.append((score, sentence, idx))
            if not scored:
                return None
            scored.sort(key=lambda x: (x[0], -x[2]), reverse=True)
            ordered: list[str] = []
            seen: set[str] = set()
            for _score, sentence, _idx in scored:
                if sentence in seen:
                    continue
                seen.add(sentence)
                ordered.append(sentence)
                if len(ordered) >= _MAX_SENTENCES:
                    break
            return ordered or None

        vecs = await embed_texts(focus_texts + [window for _, window in windows])
        if any(vec is None for vec in vecs):
            raise RuntimeError("missing transcript embeddings")

        claim_vecs = vecs[: len(focus_texts)]
        window_vecs = vecs[len(focus_texts):]

        scored: list[tuple[float, str, int]] = []
        for idx, (window_vec, (sentence, _window_text)) in enumerate(zip(window_vecs, windows)):
            score = max(sum(a * b for a, b in zip(window_vec, cv)) for cv in claim_vecs)
            if score >= _SCORE_THRESHOLD:
                scored.append((score, sentence, idx))

        scored.sort(key=lambda x: (x[0], -x[2]), reverse=True)
        ordered: list[str] = []
        seen: set[str] = set()
        for _score, sentence, _idx in scored:
            if sentence in seen:
                continue
            seen.add(sentence)
            ordered.append(sentence)
            if len(ordered) >= _MAX_SENTENCES:
                break
        return ordered or None

    except Exception as exc:
        logger.warning("Transcript embedding extraction failed, falling back to keywords: %s", exc)
        scored: list[tuple[float, str, int]] = []
        windows = _build_transcript_windows(full_text)
        for idx, (sentence, window_text) in enumerate(windows):
            score = max(_word_overlap_score(window_text, focus) for focus in focus_texts)
            if score > 0:
                scored.append((score, sentence, idx))
        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], -x[2]), reverse=True)
        ordered: list[str] = []
        seen: set[str] = set()
        for _score, sentence, _idx in scored:
            if sentence in seen:
                continue
            seen.add(sentence)
            ordered.append(sentence)
            if len(ordered) >= _MAX_SENTENCES:
                break
        return ordered or None


def _build_transcript_windows(full_text: str) -> list[tuple[str, str]]:
    """Build focal-sentence windows for transcript retrieval.

    We embed a small rolling context window instead of the bare sentence so short
    answers like "It is accelerating rapidly" keep the nearby question/topic.
    The returned tuple is (focal_sentence_for_ui, contextual_window_for_embedding).
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", full_text) if len(s.strip()) > 25]
    if not sentences:
        return []

    windows: list[tuple[str, str]] = []
    for idx, sentence in enumerate(sentences):
        start = max(0, idx - _TRANSCRIPT_LOOKBACK)
        context_parts = sentences[start : idx + 1]

        # If the previous line is an analyst question, keep it glued to the
        # answer so the answer's pronouns retain their subject.
        if idx > 0 and sentences[idx - 1].endswith("?"):
            context_parts = sentences[max(0, idx - 1) : idx + 1]
            if idx > 1:
                context_parts = sentences[max(0, idx - _TRANSCRIPT_LOOKBACK) : idx + 1]

        window = " ".join(context_parts).strip()
        if len(window) <= len(sentence):
            window = sentence
        windows.append((sentence, window))

    return windows


def extract_news_watches(claims: list[Any] | None) -> list[NewsWatch]:
    """Collect active qualitative signals from a decomposition tree.

    ``news_watch`` is explicit. ``news_topic`` and ``transcript_topic`` are
    lifted into the same watch shape so strong held-company qualitative signals
    can participate in live monitoring immediately.
    """
    watches: list[NewsWatch] = []
    for claim in claims or []:
        for entity in (claim.entities or []):
            for sig in (entity.signals or []):
                if not (sig.active and sig.signal_type in {"news_watch", "news_topic", "transcript_topic"}):
                    continue
                cfg = sig.signal_config_json or {}
                watch_for = (
                    str(
                        cfg.get("watch_for")
                        or cfg.get("topic")
                        or sig.signal_label
                        or sig.rationale
                        or ""
                    ).strip()
                )
                if watch_for:
                    raw_direction = str(cfg.get("direction") or "").strip().lower()
                    if raw_direction in {"supports", "threatens"}:
                        direction = raw_direction
                    else:
                        direction = "threatens" if getattr(entity, "relation_type", None) == "threatened_by" else "supports"
                    watches.append(
                        NewsWatch(
                            signal_id=str(sig.id),
                            claim_id=str(claim.id),
                            watch_for=watch_for,
                            direction=direction,
                            label=sig.signal_label,
                        )
                    )
    return watches


def extract_provisional_news_watches(interpretation: dict[str, Any] | None) -> list[NewsWatch]:
    """Collect qualitative watch rules from thesis interpretation before a full
    decomposition exists."""
    if not interpretation:
        return []

    hints = interpretation.get("watch_hints")
    if not isinstance(hints, list):
        return []

    watches: list[NewsWatch] = []
    for hint in hints:
        if not isinstance(hint, dict) or hint.get("kind") != "news_watch":
            continue
        watch_for = str(hint.get("watch_for") or "").strip()
        if not watch_for:
            continue
        direction = str(hint.get("direction") or "threatens").strip().lower()
        if direction not in {"threatens", "supports"}:
            direction = "threatens"
        watches.append(
            NewsWatch(
                signal_id=str(hint.get("signal_id")) if hint.get("signal_id") else None,
                claim_id=str(hint.get("claim_id")) if hint.get("claim_id") else None,
                watch_for=watch_for,
                direction=direction,
                label=str(hint.get("label")).strip() if hint.get("label") else None,
            )
        )
    return watches


async def match_thesis_news_watches(
    candidates: list[dict[str, Any]],
    news_watches: list[NewsWatch] | None,
) -> dict[int, tuple[NewsWatch, str, str]]:
    """Embed-prefilter + judge news/filing candidates against the thesis's
    news_watch conditions, tagging matches with their signal_id. MUST run before
    noise filtering, so a semantically-matched (but claim-unlinked) news item
    isn't dropped by minimum-relevance before it can be tagged. Returns the
    verdict map (id(candidate) -> (watch, severity, reason))."""
    if not news_watches:
        return {}
    candidates = await _expand_transcript_candidates_for_watches(candidates, news_watches)
    watch_texts: list[str] = []
    for watch in news_watches:
        if not watch.watch_for:
            continue
        watch_texts.extend(expand_watch_queries(watch.watch_for) or [watch.watch_for])
    if watch_texts:
        for candidate in candidates:
            if candidate.get("event_type") != "earnings_call_transcript":
                continue
            evidence = candidate.get("evidence") or {}
            full_text = evidence.get("full_transcript")
            if not isinstance(full_text, str) or not full_text.strip():
                continue
            smart = await _relevant_transcript_highlights(full_text, watch_texts)
            if not smart:
                continue
            evidence["highlights"] = smart
            evidence["excerpt"] = " ".join(smart[:2])
            evidence["topic_context"] = " ".join(smart[1:3])
    news_texts = [
        candidate_text(c) for c in candidates if c.get("event_type") in NEWS_LIKE_EVENT_TYPES
    ]
    if not news_texts:
        return {}
    similarity = await build_embedding_similarity(news_texts + [w.watch_for for w in news_watches])
    return await match_news_watches(
        candidates, news_watches, similarity=similarity, judge=judge_news_watch
    )


async def _expand_transcript_candidates_for_watches(
    candidates: list[dict[str, Any]],
    news_watches: list[NewsWatch],
) -> list[dict[str, Any]]:
    expanded = list(candidates)
    for candidate in candidates:
        if candidate.get("event_type") != "earnings_call_transcript":
            continue
        evidence = candidate.get("evidence") or {}
        full_text = evidence.get("full_transcript")
        if not isinstance(full_text, str) or not full_text.strip():
            continue

        for watch in news_watches:
            focus_texts = expand_watch_queries(watch.watch_for) or [watch.watch_for]
            smart = await _relevant_transcript_highlights(full_text, focus_texts)
            if not smart:
                continue

            topic_context_parts = [watch.label or watch.watch_for]
            topic_context_parts.extend(smart[1:3])
            expanded.append(
                {
                    **candidate,
                    "description": (
                        f"{evidence.get('quarter') or 'Latest'} earnings call on "
                        f"{watch.label or watch.watch_for}: {' '.join(smart[:2])}"
                    ).strip(),
                    "evidence": {
                        **evidence,
                        "highlights": smart,
                        "excerpt": " ".join(smart[:2]),
                        "topic_context": " ".join(part for part in topic_context_parts if part),
                    },
                }
            )
    return expanded


async def expand_transcript_candidates_for_signals(
    candidates: list[dict[str, Any]],
    claims: list[Any] | None,
) -> list[dict[str, Any]]:
    """Mirror _expand_transcript_candidates_for_watches but for every active
    signal — not just news_watch ones. AMD-style segment-commentary theses
    have signals like 'NVDA data center revenue growth' (revenue_growth type,
    no news_watch) that never used to get their own transcript candidates;
    transcript coverage of those signals was effectively zero. Now each active
    signal gets a transcript candidate seeded with its label + claim text +
    rationale and pre-bound to the signal via signal_id and matched_signal_ids,
    so downstream binding and confidence tracking don't have to re-discover
    the link.

    Designed as an addition on top of the existing watch expansion: a signal
    that already has a news_watch will get a candidate from both paths, and
    the cross-source dedup in noise_filter handles the duplicate.
    """
    if not claims:
        return candidates

    transcript_candidates = [
        c for c in candidates if c.get("event_type") == "earnings_call_transcript"
    ]
    if not transcript_candidates:
        return candidates

    # Active signal pairs (claim, signal, relation_type) — flattened. Capture
    # the scalar relation while the entity is already available so this
    # session-free pipeline never lazy-loads signal.entity later.
    active_pairs: list[tuple[Any, Any, str | None]] = []
    for claim in claims:
        for entity in getattr(claim, "entities", []) or []:
            for signal in getattr(entity, "signals", []) or []:
                if getattr(signal, "active", False):
                    active_pairs.append((claim, signal, getattr(entity, "relation_type", None)))
    if not active_pairs:
        return candidates

    expanded = list(candidates)
    for candidate in transcript_candidates:
        evidence = candidate.get("evidence") or {}
        full_text = evidence.get("full_transcript")
        if not isinstance(full_text, str) or not full_text.strip():
            continue

        for claim, signal, relation_type in active_pairs:
            label = str(getattr(signal, "signal_label", "") or "").strip()
            claim_text = str(getattr(claim, "claim_text", "") or "").strip()
            rationale = str(getattr(signal, "rationale", "") or "").strip()
            signal_type = str(getattr(signal, "signal_type", "") or "").strip()
            raw_direction = str((getattr(signal, "signal_config_json", {}) or {}).get("direction") or "").strip().lower()
            if raw_direction in {"supports", "threatens"}:
                signal_direction = raw_direction
            else:
                signal_direction = "threatens" if relation_type == "threatened_by" else "supports"
            focus_texts = [t for t in (label, claim_text, rationale) if t]
            if not focus_texts:
                continue
            smart = await _relevant_transcript_highlights(full_text, focus_texts)
            if not smart and signal_type == "transcript_topic":
                existing_highlights = evidence.get("highlights")
                existing_excerpt = str(evidence.get("excerpt") or "").strip()
                if isinstance(existing_highlights, list) and existing_highlights:
                    smart = [str(item).strip() for item in existing_highlights if str(item).strip()]
                elif existing_excerpt:
                    smart = [existing_excerpt]
            if not smart:
                continue

            sig_id = str(signal.id)
            topic_context_parts = [label or claim_text]
            topic_context_parts.extend(smart[1:3])
            expanded.append(
                {
                    **candidate,
                    "description": (
                        f"{evidence.get('quarter') or 'Latest'} earnings call on "
                        f"{label or claim_text[:60]}: {' '.join(smart[:2])}"
                    ).strip(),
                    "evidence": {
                        **evidence,
                        "signal_id": sig_id,
                        "claim_id": str(claim.id),
                        "matched_signal_ids": [sig_id],
                        "matched_signal_labels": [label] if label else [],
                        "signal_direction": signal_direction,
                        "highlights": smart,
                        "excerpt": " ".join(smart[:2]),
                        "topic_context": " ".join(part for part in topic_context_parts if part),
                    },
                }
            )
    return expanded


async def classify_candidates_for_thesis(
    thesis: Thesis,
    candidates: list[dict[str, Any]],
    *,
    investor_profile: str | None = None,
    sector: str | None = None,
    ticker: str | None = None,
    company_name: str | None = None,
    nw_matched: dict[int, tuple[NewsWatch, str, str]] | None = None,
) -> list[tuple[dict[str, Any], str, str | None]]:
    # Qualitative news_watch matches (computed before noise filtering) use the
    # judge's verdict directly instead of the generic classifier.
    nw_matched = nw_matched or {}

    classified: list[tuple[dict[str, Any], str, str | None]] = []
    for candidate in candidates:
        # Thesis-aware transcript enrichment: replace generic keyword highlights
        # with embedding-selected sentences before classification.
        if candidate.get("event_type") == "earnings_call_transcript":
            full_text = candidate.get("evidence", {}).get("full_transcript")
            if full_text:
                smart = await _thesis_aware_highlights(
                    full_text,
                    thesis.why_own_it,
                    thesis.must_remain_true,
                    thesis.what_would_change_my_mind,
                )
                if smart:
                    sentiment_label = candidate.get("evidence", {}).get("sentiment_label")
                    sentiment_suffix = f" Transcript sentiment is {sentiment_label.lower()}." if sentiment_label else ""
                    candidate = {
                        **candidate,
                        "description": (
                            f"{candidate.get('evidence', {}).get('quarter') or 'Latest'} earnings call: "
                            f"{' '.join(smart[:3])}{sentiment_suffix}"
                        ).strip(),
                        "evidence": {
                            **candidate.get("evidence", {}),
                            "highlights": smart,
                            "full_transcript": None,  # drop before storage
                        },
                    }

        # A confirmed news_watch match uses the judge's verdict directly.
        nw_match = nw_matched.get(id(candidate))
        if nw_match is not None:
            _watch, nw_severity, nw_reason = nw_match
            classified.append(
                (candidate, nw_severity, nw_reason or "This matches a condition you chose to watch for.")
            )
            continue

        classification = await classify_event(
            why_own_it=thesis.why_own_it,
            must_remain_true=thesis.must_remain_true,
            what_would_change_my_mind=thesis.what_would_change_my_mind,
            ai_summary=thesis.ai_summary,
            event_description=candidate_description_for_classifier(candidate),
            investor_profile=investor_profile,
            sector=sector,
            ticker=ticker,
            company_name=company_name,
        )
        if classification is not None and classification.severity != "skip":
            # Propagate the classifier's direction so determine_verdict can
            # surface "supports" events on the positive Held Up channel even
            # when they land at info severity — the whole reason we split
            # direction from severity in ClassificationResult. getattr guards
            # against mocked Classification objects in tests that predate
            # the direction field.
            direction = getattr(classification, "direction", None)
            if direction:
                evidence_ref = candidate.setdefault("evidence", {})
                evidence_ref["signal_direction"] = direction
            classified.append((candidate, classification.severity, classification.analysis))
            continue

        # Signal-bound transcript windows are already thesis-linked by the time
        # they reach classification: we only create them after finding a
        # signal-specific excerpt in the call. If the generic classifier still
        # returns skip/None, keep them as low-severity evidence instead of
        # dropping the support path entirely.
        evidence = candidate.get("evidence", {})
        if candidate.get("event_type") == "earnings_call_transcript" and evidence.get("signal_id"):
            classified.append(
                (
                    candidate,
                    "info",
                    "This management commentary directly touched a signal you're actively watching.",
                )
            )
            continue

        # Objective threshold breaches (a price move or metric breach past the
        # user's own threshold) fire even when the AI classifier is unavailable or
        # returns skip — numeric monitoring must not silently depend on the LLM.
        if candidate.get("event_type") in DETERMINISTIC_BREACH_EVENT_TYPES:
            classified.append((candidate, "warning", None))
            logger.info(
                "[MONITOR-DIAG] candidate preserved_without_llm reason=deterministic_threshold ticker=%s event_type=%s detail=%r",
                ticker or "",
                candidate.get("event_type", ""),
                _candidate_log_detail(candidate),
            )
            continue

        logger.info(
            "[MONITOR-DIAG] candidate dropped_after_classification reason=no_classification_result ticker=%s event_type=%s signal_id=%s claim_id=%s detail=%r",
            ticker or "",
            candidate.get("event_type", ""),
            str(candidate.get("evidence", {}).get("signal_id") or ""),
            str(candidate.get("evidence", {}).get("claim_id") or ""),
            _candidate_log_detail(candidate),
        )
    return classified


async def load_investor_profile(
    db: AsyncSession,
    user_id,
) -> str | None:
    result = await db.execute(
        select(OnboardingState.investor_profile).where(OnboardingState.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def persist_classified_candidates(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    classified: list[tuple[dict[str, Any], str, str | None]],
    claims_by_id: dict[str, Any],
    signals_by_id: dict[str, Any],
    now,
    investor_profile: str | None = None,
    persisted_events_out: list[MonitoringEvent] | None = None,
) -> list[uuid.UUID]:
    # Fast-path guard for events already visible when this transaction starts.
    anchor_rows = await db.execute(
        select(MonitoringEvent.story_anchor).where(
            MonitoringEvent.holding_id == holding.id,
            MonitoringEvent.created_at >= now - timedelta(hours=DEFAULT_COOLDOWN_HOURS),
            MonitoringEvent.story_anchor.is_not(None),
        )
    )
    recent_anchors: set[str] = set(anchor_rows.scalars().all())

    # Consistent lock order avoids deadlocks when two passes contain several of
    # the same stories in a different source order.
    ordered_classified = sorted(
        classified,
        key=lambda item: story_anchor_for_candidate(item[0]) or "",
    )

    events: list[MonitoringEvent] = []
    for candidate, severity, ai_analysis in ordered_classified:
        evidence = candidate.get("evidence", {})
        source_url = evidence.get("url")
        has_proxy_context = bool(evidence.get("proxy_ticker"))

        candidate_anchor = story_anchor_for_candidate(candidate)
        if (
            candidate_anchor
            and candidate_anchor in recent_anchors
            and _story_anchor_uses_cooldown(str(candidate.get("event_type", "")))
        ):
            logger.warning(
                "Skipped persist for holding %s: story anchor %s already persisted within %dh",
                holding.id, candidate_anchor, DEFAULT_COOLDOWN_HOURS,
            )
            continue

        if candidate_anchor:
            # PostgreSQL transaction-scoped advisory locks serialize writers
            # for the same holding + story. The second concurrent pass waits,
            # then sees the first pass's committed row before it can insert.
            await _acquire_story_anchor_lock(
                db,
                holding_id=holding.id,
                story_anchor=candidate_anchor,
            )

            event_type = str(candidate.get("event_type", ""))
            if _story_anchor_uses_cooldown(event_type):
                evidence_type = EVIDENCE_TYPE_MAP.get(event_type, event_type)
                guard_since = now - timedelta(
                    hours=COOLDOWN_HOURS.get(evidence_type, DEFAULT_COOLDOWN_HOURS)
                )
            else:
                # Coarse event types may legitimately recur later, but two jobs
                # processing the same snapshot within minutes are duplicates.
                guard_since = now - timedelta(minutes=5)

            existing_anchor = await db.execute(
                select(MonitoringEvent.id)
                .where(
                    MonitoringEvent.holding_id == holding.id,
                    MonitoringEvent.story_anchor == candidate_anchor,
                    MonitoringEvent.created_at >= guard_since,
                )
                .limit(1)
            )
            if existing_anchor.scalar_one_or_none() is not None:
                logger.warning(
                    "Skipped concurrent duplicate for holding %s: story anchor %s",
                    holding.id,
                    candidate_anchor,
                )
                recent_anchors.add(candidate_anchor)
                continue

        evidence_signal_id = evidence.get("signal_id")
        evidence_claim_id = evidence.get("claim_id")
        claim_obj = claims_by_id.get(evidence_claim_id) if evidence_claim_id else None
        signal_obj = signals_by_id.get(evidence_signal_id) if evidence_signal_id else None

        verdict = determine_verdict(severity, candidate)
        if claim_obj is None and signal_obj is None:
            if (
                candidate.get("event_type") == "analyst_revision"
                and evidence.get("signal_direction") not in {"supports", "threatens"}
            ):
                logger.info(
                    "[MONITOR-DIAG] candidate dropped_before_persistence reason=unlinked_analyst_revision_without_direction holding_id=%s thesis_id=%s event_type=%s severity=%s verdict=%s detail=%r",
                    holding.id,
                    thesis.id,
                    candidate.get("event_type", ""),
                    severity,
                    verdict,
                    _candidate_log_detail(candidate),
                )
                continue
            if candidate.get("event_type") == "earnings_surprise" and not has_proxy_context:
                logger.info(
                    "[MONITOR-DIAG] candidate dropped_before_persistence reason=unlinked_earnings_surprise_without_proxy holding_id=%s thesis_id=%s event_type=%s severity=%s verdict=%s detail=%r",
                    holding.id,
                    thesis.id,
                    candidate.get("event_type", ""),
                    severity,
                    verdict,
                    _candidate_log_detail(candidate),
                )
                continue
            if (
                candidate.get("event_type") in (NEWS_LIKE_EVENT_TYPES - {"edgar_8k", "earnings_call_transcript"})
                and verdict == "neutral"
            ):
                logger.info(
                    "[MONITOR-DIAG] candidate dropped_before_persistence reason=unlinked_neutral_news_like_event holding_id=%s thesis_id=%s event_type=%s severity=%s verdict=%s detail=%r",
                    holding.id,
                    thesis.id,
                    candidate.get("event_type", ""),
                    severity,
                    verdict,
                    _candidate_log_detail(candidate),
                )
                continue

        evidence_summary = build_evidence_summary(
            candidate=candidate,
            claim_text=claim_obj.claim_text if claim_obj else None,
            signal_label=signal_obj.signal_label if signal_obj else None,
            why_own_it=thesis.why_own_it,
            severity=severity,
            verdict=verdict,
            investor_profile=investor_profile,
        )
        evidence_type = EVIDENCE_TYPE_MAP.get(candidate["event_type"], candidate["event_type"])
        stored_summary = candidate_summary_for_storage(candidate)

        event = MonitoringEvent(
            # Explicit id so the conviction-log entry below can reference the
            # event before the flush assigns defaults.
            id=uuid.uuid4(),
            holding_id=holding.id,
            thesis_id=thesis.id,
            event_type=candidate["event_type"],
            severity=severity,
            title=_event_title(holding.ticker, candidate, claim_obj),
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
            story_anchor=candidate_anchor,
            evidence_summary=evidence_summary,
            verdict=verdict,
        )
        db.add(event)
        events.append(event)
        logger.info(
            "[MONITOR-DIAG] event persisted holding_id=%s thesis_id=%s event_id=%s event_type=%s severity=%s verdict=%s signal_id=%s claim_id=%s detail=%r",
            holding.id,
            thesis.id,
            event.id,
            event.event_type,
            event.severity,
            event.verdict,
            str(event.signal_id or ""),
            str(event.claim_id or ""),
            _candidate_log_detail(candidate),
        )
        if candidate_anchor:
            recent_anchors.add(candidate_anchor)
        # Mark cooldown on every matched signal, not just the primary, so a
        # multi-pillar article doesn't fire warnings on the same Services
        # margin signal again next pass just because it was a "secondary"
        # binding this time.
        matched_signal_ids = evidence.get("matched_signal_ids")
        fired_ids = list(matched_signal_ids) if isinstance(matched_signal_ids, list) else []
        if not fired_ids and evidence_signal_id:
            fired_ids = [evidence_signal_id]
        seen_fired: set[str] = set()
        for fired_id in fired_ids:
            fired_id_str = str(fired_id)
            if not fired_id_str or fired_id_str in seen_fired:
                continue
            seen_fired.add(fired_id_str)
            await record_signal_fired(fired_id_str, signals_by_id, now=now)
        append_log_entry(
            db,
            thesis_id=thesis.id,
            holding_id=holding.id,
            user_id=thesis.user_id,
            entry_type=EVIDENCE_RECEIVED,
            content=evidence_summary or stored_summary[:300],
            metadata={
                "event_type": candidate["event_type"],
                "severity": severity,
                "event_id": str(event.id),
            },
            claim_id=uuid.UUID(evidence_claim_id) if evidence_claim_id else None,
            signal_id=uuid.UUID(evidence_signal_id) if evidence_signal_id else None,
        )

        if severity == "thesis_breaking" and thesis.status in ("active", "draft"):
            thesis.status = "needs_review"

    if events:
        await db.flush()
        if persisted_events_out is not None:
            persisted_events_out.extend(events)
        from app.services.relevance import log_event_fired

        for event in events:
            log_event_fired(event, ticker=holding.ticker)
    return [event.id for event in events]
