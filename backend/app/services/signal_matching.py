from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
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


# Event types whose candidate text is meaningful to compare against signal
# labels via embeddings. Quantitative events (price_move, watch_hint_breach,
# metric_threshold, earnings_surprise) are already pre-bound to a specific
# signal; embeddings can't add anything useful there.
_EMBEDDING_MATCH_EVENT_TYPES = {
    "news_or_earnings_candidate",
    "product_ramp_update",
    "news_keyword_match",
    "edgar_8k",
    "gemini_news",
    "contract_renewal_update",
    "funding_condition_update",
    "margin_pressure_update",
    "customer_capex_signal",
    "earnings_call_transcript",
}

# Cosine floor for the embedding pre-filter. Tuned to be conservative:
# embeddings between two random pieces of text typically sit around 0.2-0.3;
# 0.6 catches semantic matches even when there's no word overlap (e.g. "Apple
# Pricing Dilemma" vs "Services gross margin trend") while staying well above
# random-noise territory.
DEFAULT_EMBEDDING_SIMILARITY_FLOOR = 0.6


def _candidate_embedding_text(candidate: dict[str, Any]) -> str:
    """Compact text representation used for embedding a candidate. Falls back
    through headline, summary, and description to handle the various event
    shapes (Gemini news, yfinance items, EDGAR filings, transcripts)."""
    evidence = candidate.get("evidence") or {}
    parts = [
        evidence.get("headline"),
        evidence.get("summary"),
        evidence.get("description"),
        candidate.get("description"),
    ]
    text = " ".join(str(p).strip() for p in parts if p).strip()
    # Hard-cap to keep the embedding token budget bounded on very long
    # transcript chunks; 1500 chars is plenty for semantic similarity.
    return text[:1500]


def _signal_embedding_text(signal: "ThesisSignal", claim: "ThesisClaim") -> str:
    """Compose the text used to embed a signal — the label plus claim
    context so 'AAPL Services gross margin trend' is anchored to 'Services
    gross margin stays above 72%'."""
    parts = [
        getattr(signal, "signal_label", None),
        getattr(claim, "claim_text", None),
        getattr(signal, "rationale", None),
    ]
    return " ".join(str(p).strip() for p in parts if p).strip()


async def enrich_candidates_with_embedding_matches(
    candidates: list[dict[str, Any]],
    claims: list[Any] | None,
    *,
    similarity_floor: float = DEFAULT_EMBEDDING_SIMILARITY_FLOOR,
) -> list[dict[str, Any]]:
    """Add embedding-based signal matches to candidates that match_candidates_to_signals
    has already processed. The union of (Gemini explicit labels) ∪ (word-overlap
    matches) ∪ (embedding matches above floor) becomes the final multi-binding.

    Designed as an on-demand layer:
    - no persisted signal embeddings (build_embedding_similarity in news_watch.py
      embeds on the fly via OpenAI), so no schema migration required
    - falls back to word-overlap if the embedding call fails, so a provider
      outage degrades gracefully
    - skipped for event types where embeddings can't add value (price_move,
      watch_hint_breach, etc — already pre-bound).
    """
    if not candidates or not claims:
        return candidates
    active_signals = _collect_active_signals(claims)
    if not active_signals:
        return candidates

    targets = [
        c for c in candidates
        if c.get("event_type") in _EMBEDDING_MATCH_EVENT_TYPES
        and _candidate_embedding_text(c)
    ]
    if not targets:
        return candidates

    # Build the embedding similarity function once for the full text corpus
    # (signal texts + candidate texts). Single embeddings call for the whole
    # batch, then sync similarity lookups.
    from app.services.news_watch import build_embedding_similarity

    signal_texts = {
        str(signal.id): _signal_embedding_text(signal, claim)
        for claim, signal in active_signals
    }
    candidate_texts = {id(c): _candidate_embedding_text(c) for c in targets}
    all_texts = list(signal_texts.values()) + list(candidate_texts.values())
    similarity = await build_embedding_similarity(all_texts)

    signal_by_id = {str(signal.id): (claim, signal) for claim, signal in active_signals}

    for candidate in targets:
        evidence = candidate.setdefault("evidence", {})
        cand_text = candidate_texts[id(candidate)]
        existing_ids = {str(value) for value in (evidence.get("matched_signal_ids") or [])}
        added: list[tuple[str, str, float]] = []
        for sig_id, sig_text in signal_texts.items():
            if sig_id in existing_ids or not sig_text:
                continue
            score = similarity(cand_text, sig_text)
            if score < similarity_floor:
                continue
            _, signal = signal_by_id[sig_id]
            label = str(getattr(signal, "signal_label", "") or "").strip()
            added.append((sig_id, label, score))
            existing_ids.add(sig_id)
        if not added:
            continue
        added.sort(key=lambda row: row[2], reverse=True)
        evidence["matched_signal_ids"] = list(evidence.get("matched_signal_ids") or []) + [sid for sid, _, _ in added]
        existing_labels = list(evidence.get("matched_signal_labels") or [])
        evidence["matched_signal_labels"] = existing_labels + [label for _, label, _ in added if label]
        # Preserve the cosine score so the UI can render high-confidence
        # (Gemini explicit label or strong semantic match) differently from
        # weakly-inferred matches. Cosine sits in [0,1] for unit vectors which
        # is the contract OpenAI's text-embedding-3-small returns.
        confidence_map = evidence.setdefault("match_confidence_by_signal", {})
        if not isinstance(confidence_map, dict):
            confidence_map = {}
            evidence["match_confidence_by_signal"] = confidence_map
        for sig_id, _, score in added:
            confidence_map[sig_id] = round(float(score), 3)
        # If the candidate had nothing bound before, pick the highest-similarity
        # new match as the primary signal_id so downstream readers that still
        # use the single anchor get something useful.
        if not evidence.get("signal_id"):
            evidence["signal_id"] = added[0][0]

    return candidates


# LLM adjudication runs on the middle cosine band: above the ceiling we trust
# the embedding match outright (huge cosine on dense text == clear semantic
# overlap), below the floor we trust the rejection (too far apart to be worth
# the LLM call). The band is where the call adds the most signal — borderline
# matches that semantic similarity alone can't reliably decide.
ADJUDICATION_FLOOR = 0.50
ADJUDICATION_CEILING = 0.85

# Bound the LLM cost. A busy news day shouldn't fan out into an unbounded
# number of paid calls; the user can always re-run check-now if they want
# deeper coverage.
DEFAULT_MAX_ADJUDICATIONS_PER_CANDIDATE = 5
DEFAULT_MAX_ADJUDICATIONS_PER_BATCH = 25

_ADJUDICATION_MODEL = "gpt-4o-mini"

_ADJUDICATION_PROMPT = """You are scoring whether a news item provides evidence about a specific watch signal an investor cares about.

Watch signal: "{signal_label}"
From the claim: "{claim_text}"

News item:
"{headline}: {summary}"

Score 0.0 to 1.0:
- 1.0 = clear, direct evidence the watch signal is being tested
- 0.7 = news touches the signal's topic and is meaningfully relevant
- 0.4 = tangentially related; could be relevant but not direct
- 0.0 = no real connection to this specific watch signal

Return a single JSON object: {{"confidence": 0.0-1.0}}. No prose."""


async def _adjudicate_one(client, *, signal_label: str, claim_text: str, headline: str, summary: str) -> float | None:
    """Single LLM call. Returns confidence 0-1 on success, None on failure
    (caller keeps the cosine score in that case)."""
    import json

    prompt = _ADJUDICATION_PROMPT.format(
        signal_label=(signal_label or "").strip(),
        claim_text=(claim_text or "").strip()[:200],
        headline=(headline or "").strip()[:200],
        summary=(summary or "").strip()[:400],
    )
    try:
        response = await client.chat.completions.create(
            model=_ADJUDICATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=64,
            response_format={"type": "json_object"},
            timeout=15.0,
        )
        raw = (response.choices[0].message.content or "{}").strip()
        parsed = json.loads(raw)
    except Exception:
        return None
    confidence = parsed.get("confidence")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))


async def adjudicate_signal_matches(
    candidates: list[dict[str, Any]],
    claims: list[Any] | None,
    *,
    floor: float = ADJUDICATION_FLOOR,
    ceiling: float = ADJUDICATION_CEILING,
    drop_threshold: float = 0.45,
    max_per_candidate: int = DEFAULT_MAX_ADJUDICATIONS_PER_CANDIDATE,
    max_per_batch: int = DEFAULT_MAX_ADJUDICATIONS_PER_BATCH,
) -> list[dict[str, Any]]:
    """LLM-refine the borderline embedding matches.

    For each candidate, finds matches whose cosine sits in the medium band
    [floor, ceiling] and asks gpt-4o-mini whether the evidence really touches
    that signal. The LLM's confidence replaces the cosine score in
    match_confidence_by_signal. Matches that come back below drop_threshold
    are removed from matched_signal_ids and matched_signal_labels.

    Bounded by max_per_candidate and max_per_batch so a busy thesis can't fan
    out into unbounded LLM cost. Falls back to existing cosine bindings on any
    LLM failure (None confidence from _adjudicate_one is treated as no-op).
    """
    if not candidates or not claims or not settings.openai_api_key:
        return candidates

    # Collect per-candidate work items in the cosine band, capped per candidate.
    work: list[tuple[dict[str, Any], str, str, str]] = []  # (evidence, sig_id, label, claim_text_for_prompt)
    claim_by_signal: dict[str, str] = {}
    label_by_signal: dict[str, str] = {}
    active_signals = _collect_active_signals(claims)
    for claim, signal in active_signals:
        sid = str(signal.id)
        claim_by_signal[sid] = str(getattr(claim, "claim_text", "") or "")
        label_by_signal[sid] = str(getattr(signal, "signal_label", "") or "")

    for candidate in candidates:
        if candidate.get("event_type") not in _EMBEDDING_MATCH_EVENT_TYPES:
            continue
        evidence = candidate.get("evidence") or {}
        if not isinstance(evidence, dict):
            continue
        confidence_map = evidence.get("match_confidence_by_signal")
        if not isinstance(confidence_map, dict):
            continue
        # Identify borderline signals — sorted by cosine descending so the
        # per-candidate cap takes the closest-to-confident ones first.
        band_pairs = sorted(
            (
                (sid, float(score))
                for sid, score in confidence_map.items()
                if floor <= float(score) < ceiling
            ),
            key=lambda row: row[1],
            reverse=True,
        )[:max_per_candidate]
        if not band_pairs:
            continue
        headline = str((evidence.get("headline") or candidate.get("description") or "")).strip()
        summary = str(evidence.get("summary") or "").strip()
        for sid, _ in band_pairs:
            work.append((evidence, sid, headline, summary))
            if len(work) >= max_per_batch:
                break
        if len(work) >= max_per_batch:
            break

    if not work:
        return candidates

    try:
        from openai import AsyncOpenAI
    except ImportError:
        return candidates
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    import asyncio as _asyncio
    judgments = await _asyncio.gather(
        *(
            _adjudicate_one(
                client,
                signal_label=label_by_signal.get(sid, ""),
                claim_text=claim_by_signal.get(sid, ""),
                headline=headline,
                summary=summary,
            )
            for _, sid, headline, summary in work
        ),
        return_exceptions=False,
    )

    # Apply each judgment back onto the corresponding candidate.
    for (evidence, sid, _, _), confidence in zip(work, judgments):
        if confidence is None:
            continue
        confidence_map = evidence.get("match_confidence_by_signal")
        if isinstance(confidence_map, dict):
            confidence_map[sid] = round(confidence, 3)
        if confidence < drop_threshold:
            ids = evidence.get("matched_signal_ids")
            if isinstance(ids, list):
                remaining_ids = [str(x) for x in ids if str(x) != sid]
                evidence["matched_signal_ids"] = remaining_ids
                evidence["matched_signal_labels"] = [
                    label_by_signal.get(remaining_sid, "")
                    for remaining_sid in remaining_ids
                    if label_by_signal.get(remaining_sid, "")
                ]
            if isinstance(confidence_map, dict):
                confidence_map.pop(sid, None)
            # If we just dropped the primary signal_id, promote the next-best
            # match (highest remaining cosine/LLM confidence) so consumers
            # still get an anchor.
            if evidence.get("signal_id") == sid:
                remaining = evidence.get("matched_signal_ids") or []
                evidence["signal_id"] = remaining[0] if remaining else None

    return candidates


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
    existing_ids_raw = evidence.get("matched_signal_ids")
    existing_labels_raw = evidence.get("matched_signal_labels")
    merged_ids = [str(x) for x in existing_ids_raw] if isinstance(existing_ids_raw, list) else []
    merged_labels = [str(x) for x in existing_labels_raw if isinstance(x, str)] if isinstance(existing_labels_raw, list) else []
    primary_label = ""
    for _, signal in active_signals:
        if str(signal.id) == str(primary_id):
            primary_label = str(getattr(signal, "signal_label", None) or "").strip()
            break
    primary_id_str = str(primary_id)
    if primary_id_str in merged_ids:
        merged_ids = [sid for sid in merged_ids if sid != primary_id_str]
    merged_ids.insert(0, primary_id_str)
    if primary_label:
        merged_labels = [label for label in merged_labels if label != primary_label]
        merged_labels.insert(0, primary_label)

    relevant_labels = evidence.get("relevant_signals")
    if isinstance(relevant_labels, list):
        wanted = {_normalize_text(str(lbl)) for lbl in relevant_labels if str(lbl).strip()}
        if wanted:
            for _, signal in active_signals:
                sid = str(signal.id)
                label = str(getattr(signal, "signal_label", None) or "").strip()
                if not label or _normalize_text(label) not in wanted:
                    continue
                if sid not in merged_ids:
                    merged_ids.append(sid)
                if label not in merged_labels:
                    merged_labels.append(label)

    evidence["matched_signal_ids"] = merged_ids
    if merged_labels:
        evidence["matched_signal_labels"] = merged_labels


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
        if overlap <= 0:
            return 0
        family_bonus = 2 if signal_type in NEWS_SIGNAL_TYPES else 0
        return family_bonus + overlap * 10

    return 0


def _signal_match_text(claim: ThesisClaim, signal: ThesisSignal) -> str:
    signal_label = getattr(signal, "signal_label", None)
    signal_label = _strip_leading_ticker_token(str(signal_label).strip()) if signal_label else None
    parts = [
        signal_label,
        getattr(signal, "rationale", None),
        getattr(claim, "claim_text", None),
        str(getattr(signal, "signal_type", "") or "").replace("_", " "),
    ]
    return " ".join(str(part).strip() for part in parts if part).strip()


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w{3,}", text.lower()))


def _normalize_text(text: str) -> str:
    return " ".join(_words(text))


def _strip_leading_ticker_token(text: str) -> str:
    if not text:
        return text
    parts = text.split()
    if parts and re.fullmatch(r"[A-Z0-9._-]{1,5}", parts[0]):
        return " ".join(parts[1:]).strip()
    return text


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
    if verdict == "supports":
        if watched_text:
            return f"This supports the part of the thesis tied to {watched_text}."
        return "This supports the original investment case."
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
    if verdict == "supports":
        return "No decision needed. Keep watching for the next test of this part of the case."
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

    # The classifier can emit a direction alongside severity ("supports" /
    # "threatens" / "neutral") — see ClassificationResult in ai_monitor. The
    # direction path lets a low-severity event that clearly validates a
    # stated pillar surface as "supports" on the Held Up channel instead of
    # vanishing as info/neutral (the transcript FYI problem). Direction
    # wins over the severity fallback whenever the LLM was confident about
    # which way this cuts against the thesis.
    signal_direction = evidence.get("signal_direction")
    if signal_direction == "supports":
        return "supports"
    if signal_direction == "threatens":
        # Warning + threatens is more precise than the generic "review";
        # info + threatens still deserves a "review" nudge over neutral.
        if severity in {"thesis_breaking", "warning"}:
            return "threatens"
        return "review"

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
