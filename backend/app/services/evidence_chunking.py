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


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if len(part.strip()) > 25]


def _transcript_chunks(candidate: dict[str, Any]) -> list[tuple[str, str]]:
    evidence = candidate.get("evidence", {})
    full_text = str(evidence.get("full_transcript") or "").strip()
    if not full_text:
        highlights = evidence.get("highlights")
        if isinstance(highlights, list):
            full_text = " ".join(str(item).strip() for item in highlights if str(item).strip())
    if not full_text:
        excerpt = str(evidence.get("excerpt") or "").strip()
        full_text = excerpt
    sentences = _split_sentences(full_text)
    if not sentences and full_text:
        return [("transcript_excerpt", full_text[:1500])]
    chunks: list[tuple[str, str]] = []
    for idx, sentence in enumerate(sentences):
        start = max(0, idx - _TRANSCRIPT_WINDOW)
        end = min(len(sentences), idx + _TRANSCRIPT_WINDOW + 1)
        window = " ".join(sentences[start:end]).strip()
        if window:
            chunks.append(("transcript_window", window[:2000]))
    return chunks[:12]


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

    keys = [(source_type, source_id, idx) for source_type, source_id, idx, _chunk_type, _text in prepared]
    existing = await db.execute(
        select(EvidenceChunk.source_type, EvidenceChunk.source_id, EvidenceChunk.chunk_index).where(
            EvidenceChunk.thesis_id == thesis.id,
            EvidenceChunk.holding_id == holding.id,
            tuple_(EvidenceChunk.source_type, EvidenceChunk.source_id, EvidenceChunk.chunk_index).in_(keys),
        )
    )
    existing_keys = {(row[0], row[1], row[2]) for row in existing.all()}

    new_rows = [row for row in prepared if (row[0], row[1], row[2]) not in existing_keys]
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
                metadata_json={"event_type": source_type},
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
