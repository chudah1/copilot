from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_chunk import EvidenceChunk
from app.models.holding import Holding
from app.models.thesis import Thesis
from app.services.embeddings import embed_text_map

logger = logging.getLogger(__name__)

_NEWS_EVENT_TYPES = {
    "gemini_news",
    "news_or_earnings_candidate",
    "product_ramp_update",
    "contract_renewal_update",
    "funding_condition_update",
    "margin_pressure_update",
    "customer_capex_signal",
    "news_keyword_match",
}
_TRANSCRIPT_WINDOW = 2
_NEWS_TRUSTED_SOURCES = {"gemini_search"}
_GENERIC_NEWS_MIN_RELEVANCE = 0.35


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if len(part.strip()) > 25]


def _dedupe_chunks(chunks: list[tuple[str, str]], *, limit: int) -> list[tuple[str, str]]:
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for chunk_type, chunk_text in chunks:
        normalized = " ".join(chunk_text.split())
        key = (chunk_type, normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        deduped.append((chunk_type, chunk_text))
        if len(deduped) >= limit:
            break
    return deduped


def _transcript_qa_chunks(sentences: list[str]) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    for idx, sentence in enumerate(sentences):
        if not sentence.endswith("?"):
            continue
        start = max(0, idx - 1)
        end = min(len(sentences), idx + 3)
        window = " ".join(sentences[start:end]).strip()
        if window:
            chunks.append(("transcript_qa", window[:1800]))
    return chunks


def _transcript_chunks(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    evidence = candidate.get("evidence", {})
    chunks: list[tuple[str, str]] = []
    excerpt = str(evidence.get("excerpt") or "").strip()
    topic_context = str(evidence.get("topic_context") or "").strip()
    highlights = evidence.get("highlights")
    focus_parts: list[str] = []
    if topic_context:
        focus_parts.append(f"Topic context: {topic_context}")
    if excerpt:
        focus_parts.append(excerpt)
        chunks.append(("transcript_highlight", excerpt[:1200]))
    elif isinstance(highlights, list):
        focus_parts.extend(str(item).strip() for item in highlights[:3] if str(item).strip())
    focus_text = "\n".join(part for part in focus_parts if part).strip()
    if focus_text:
        chunks.append(("transcript_focus", focus_text[:1500]))
    if isinstance(highlights, list):
        for highlight in highlights[:4]:
            highlight_text = str(highlight).strip()
            if highlight_text:
                chunks.append(("transcript_highlight", highlight_text[:1200]))

    full_text = str(evidence.get("full_transcript") or "").strip()
    if not full_text:
        highlights = evidence.get("highlights")
        if isinstance(highlights, list):
            full_text = " ".join(str(item).strip() for item in highlights if str(item).strip())
    if not full_text:
        full_text = excerpt
    sentences = _split_sentences(full_text)
    if not sentences and full_text:
        if not chunks:
            chunks.append(("transcript_excerpt", full_text[:1500]))
        return _dedupe_chunks(chunks, limit=12)
    chunks.extend(_transcript_qa_chunks(sentences))
    for idx, sentence in enumerate(sentences):
        start = max(0, idx - _TRANSCRIPT_WINDOW)
        end = min(len(sentences), idx + _TRANSCRIPT_WINDOW + 1)
        window = " ".join(sentences[start:end]).strip()
        if window:
            chunks.append(("transcript_window", window[:2000]))
    return _dedupe_chunks(chunks, limit=12)


def _edgar_chunks(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    evidence = candidate.get("evidence", {})
    extracted = evidence.get("extracted") or {}
    chunks: list[tuple[str, str]] = []
    key_quote = str(extracted.get("key_quote") or "").strip()
    rationale = str(extracted.get("verdict_rationale") or "").strip()
    item_summary = str(extracted.get("item_summary") or "").strip()
    if key_quote:
        chunks.append(("edgar_key_quote", key_quote[:2000]))
    if rationale:
        chunks.append(("edgar_rationale", rationale[:2000]))
    if item_summary:
        chunks.append(("edgar_item_summary", item_summary[:2000]))
    item_summaries = extracted.get("item_summaries")
    if isinstance(item_summaries, dict):
        for item, summary in list(item_summaries.items())[:6]:
            text = str(summary or "").strip()
            if text:
                chunks.append((f"edgar_item_{item}", text[:2000]))
    if not chunks:
        description = str(candidate.get("description") or evidence.get("description") or "").strip()
        if description:
            chunks.append(("edgar_description", description[:1500]))
    return chunks


def _news_chunks(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    if not _should_persist_news_candidate(candidate):
        return []
    evidence = candidate.get("evidence", {})
    headline = str(evidence.get("headline") or "").strip()
    summary = str(evidence.get("summary") or "").strip()
    topic_context = str(evidence.get("topic_context") or "").strip()
    body = "\n".join(part for part in (headline, summary, topic_context) if part).strip()
    if not body:
        body = str(candidate.get("description") or "").strip()
    if not body:
        return []
    return [("news_summary", body[:1500])]


def _should_persist_news_candidate(candidate: dict[str, Any]) -> bool:
    event_type = str(candidate.get("event_type") or "")
    evidence = candidate.get("evidence", {})
    source = str(evidence.get("source") or "").strip().lower()
    relevance = str(evidence.get("relevance") or "").strip().lower()
    grounded = bool(evidence.get("is_grounded"))
    ticker_relevance = evidence.get("ticker_relevance")
    try:
        ticker_relevance_value = float(ticker_relevance) if ticker_relevance is not None else None
    except (TypeError, ValueError):
        ticker_relevance_value = None

    relevant_signals = evidence.get("relevant_signals")
    matched_signal_ids = evidence.get("matched_signal_ids")
    matched_topics = evidence.get("matched_topics")
    topic_context = str(evidence.get("topic_context") or "").strip()

    explicitly_bound = bool(isinstance(relevant_signals, list) and relevant_signals)
    semantically_bound = bool(isinstance(matched_signal_ids, list) and matched_signal_ids)
    topic_shaped = bool(isinstance(matched_topics, list) and matched_topics) or bool(topic_context)
    trusted_source = source in _NEWS_TRUSTED_SOURCES or grounded
    strong_relevance = relevance == "high" or (
        ticker_relevance_value is not None and ticker_relevance_value >= _GENERIC_NEWS_MIN_RELEVANCE
    )

    if event_type == "gemini_news":
        return explicitly_bound or trusted_source
    if event_type == "news_or_earnings_candidate":
        return explicitly_bound or semantically_bound or trusted_source or strong_relevance
    return explicitly_bound or semantically_bound or topic_shaped or trusted_source or strong_relevance


def build_candidate_chunks(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    event_type = str(candidate.get("event_type") or "")
    if event_type == "earnings_call_transcript":
        return _transcript_chunks(candidate)
    if event_type == "edgar_8k":
        return _edgar_chunks(candidate)
    if event_type in _NEWS_EVENT_TYPES:
        return _news_chunks(candidate)
    return []


def _source_identity(candidate: dict[str, Any]) -> tuple[str, str | None]:
    event_type = str(candidate.get("event_type") or "")
    evidence = candidate.get("evidence", {})
    if event_type == "earnings_call_transcript":
        source_id = str(evidence.get("transcript_id") or "").strip() or None
        signal_id = str(evidence.get("signal_id") or "").strip()
        if source_id and signal_id:
            source_id = f"{source_id}:{signal_id}"
        return "earnings_call_transcript", source_id
    if event_type == "edgar_8k":
        source_id = str(evidence.get("edgar_accession") or "").strip() or None
        return "edgar_8k", source_id
    if event_type in _NEWS_EVENT_TYPES:
        source_id = (
            str(evidence.get("article_id") or "").strip()
            or str(evidence.get("url") or "").strip()
            or None
        )
        return event_type, source_id
    return event_type, None


def _fallback_source_id(source_type: str, text: str) -> str:
    return f"{source_type}:{hashlib.sha256(text.encode()).hexdigest()[:24]}"


def _chunk_metadata(candidate: dict[str, Any], source_type: str) -> dict[str, Any]:
    evidence = candidate.get("evidence", {})
    metadata: dict[str, Any] = {
        "event_type": source_type,
        "source": evidence.get("source"),
        "relevance": evidence.get("relevance"),
        "is_grounded": bool(evidence.get("is_grounded")),
        "ticker_relevance": evidence.get("ticker_relevance"),
        "topic_context": evidence.get("topic_context"),
        "matched_topics": evidence.get("matched_topics"),
        "relevant_signals": evidence.get("relevant_signals"),
        "matched_signal_ids": evidence.get("matched_signal_ids"),
        "matched_signal_labels": evidence.get("matched_signal_labels"),
        "signal_id": evidence.get("signal_id"),
        "claim_id": evidence.get("claim_id"),
    }
    return {key: value for key, value in metadata.items() if value not in (None, "", [], {})}


async def persist_candidate_evidence_chunks(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    candidates: list[dict[str, Any]],
) -> int:
    prepared: list[tuple[str, str, int, str, str]] = []
    for candidate in candidates:
        source_type, source_id = _source_identity(candidate)
        chunks = build_candidate_chunks(candidate)
        for idx, (chunk_type, chunk_text) in enumerate(chunks):
            stable_source_id = source_id or _fallback_source_id(source_type, chunk_text)
            prepared.append((source_type, stable_source_id, idx, chunk_type, chunk_text))

    if not prepared:
        return 0

    keys = [
        (source_type, source_id, idx, chunk_type)
        for source_type, source_id, idx, chunk_type, _text in prepared
    ]
    existing = await db.execute(
        select(
            EvidenceChunk.source_type,
            EvidenceChunk.source_id,
            EvidenceChunk.chunk_index,
            EvidenceChunk.chunk_type,
        ).where(
            EvidenceChunk.thesis_id == thesis.id,
            EvidenceChunk.holding_id == holding.id,
            tuple_(
                EvidenceChunk.source_type,
                EvidenceChunk.source_id,
                EvidenceChunk.chunk_index,
                EvidenceChunk.chunk_type,
            ).in_(keys),
        )
    )
    existing_keys = {(row[0], row[1], row[2], row[3]) for row in existing.all()}

    new_rows = [row for row in prepared if (row[0], row[1], row[2], row[3]) not in existing_keys]
    if not new_rows:
        return 0

    text_map = await embed_text_map([row[4] for row in new_rows])
    now = datetime.now(timezone.utc)
    for source_type, source_id, idx, chunk_type, chunk_text in new_rows:
        db.add(
            EvidenceChunk(
                thesis_id=thesis.id,
                holding_id=holding.id,
                ticker=holding.ticker,
                source_type=source_type,
                source_id=source_id,
                chunk_type=chunk_type,
                chunk_index=idx,
                chunk_text=chunk_text,
                metadata_json=_chunk_metadata(candidate, source_type),
                embedding=text_map.get(chunk_text),
                embedded_at=now if text_map.get(chunk_text) else None,
            )
        )
    return len(new_rows)


async def best_effort_persist_candidate_evidence_chunks(
    db: AsyncSession,
    *,
    thesis: Thesis,
    holding: Holding,
    candidates: list[dict[str, Any]],
) -> int:
    try:
        return await persist_candidate_evidence_chunks(db, thesis=thesis, holding=holding, candidates=candidates)
    except Exception as exc:  # pragma: no cover - defensive non-blocking path
        logger.warning("Evidence chunk persistence failed for thesis %s: %s", thesis.id, exc)
        return 0
